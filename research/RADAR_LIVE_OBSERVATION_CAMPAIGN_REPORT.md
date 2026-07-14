# Decision Radar live observation campaign v2

Generated at `2026-07-14T16:33:07.863847+00:00` from local artifacts only.
Research and decision support only. This report contains no trade recommendation.

## Campaign measurement

- Status: `in_progress_baseline_warming`
- Counted real/no-send cycles: `6`
- Real Decision candidates: `2`
- Provider failures: `0`
- Preflight/blocked attempts: `1`
- Event Alpha catalyst burn-in: `separate_not_aggregated`
- Historical market-provenance v2 fields: `read_only_adapter`

### Decision routes

- `risk_watch`: `2`

## Authority and pointer

- Pointer status: `authoritative`
- Current namespace: `radar_market_no_send_20260714t163300z`
- Exact run: `2026-07-14T16:33:00.405079+00:00|no_key_live`
- Revision: `12`
- Exact operator binding: `true`

### Authoritative generations

| Namespace | Observed at | Candidates | Routes | Current |
|---|---|---:|---|---|
| radar_market_no_send_20260713t190728z | 2026-07-13T19:07:29.084694+00:00 | 0 | none | false |
| radar_market_no_send_20260714t002940z | 2026-07-14T00:29:40.814498+00:00 | 1 | risk_watch=1 | false |
| radar_market_no_send_20260714t102122z | 2026-07-14T10:21:23.140944+00:00 | 0 | none | false |
| radar_market_no_send_20260714t163300z | 2026-07-14T16:33:00.405079+00:00 | 0 | none | true |

### Complete but non-authoritative generations

| Namespace | Observed at | Candidates | Routes | Current |
|---|---|---:|---|---|
| radar_market_no_send | 2026-07-13T15:17:06.228233+00:00 | 0 | none | false |
| radar_market_no_send_20260713t152704z | 2026-07-13T15:27:13.330145+00:00 | 1 | risk_watch=1 | false |

## Baseline maturity

- Status: `warming`
- Retained observations: `180`
- Baseline-counted observations: `150`
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

- **execution_quality_spread:** Trusted spread coverage is 0/180. Provider selection is deferred until the operator identifies the intended execution venue.
- **proxy_market_features:** The campaign retains 540 proxy feature observations; proxy evidence remains explicitly quality-capped.
- **temporal_baseline_maturity:** The required feature/time-aware temporal baseline is not globally warm.

## Next observation

- Next eligible time: `2026-07-14T17:33:00.405079+00:00`
- Eligible at report time: `false`
- Exact next safe operator command: `make radar-market-no-send-readiness PYTHON=.venv/bin/python`
- Authorization is rechecked at the provider boundary; this report never creates or changes it.

## Campaign-v2 conclusion

Decision Radar campaign v2 has 6 counted real/no-send cycles and 2 canonical ideas; 1 outcome is pending and 1 are matured. There are 0 provider failures and 1 blocked/preflight attempts. Baseline status is warming with 0/33 warm assets. Pointer history contains 4 bound generations and current authority is radar_market_no_send_20260714t163300z. Data-quality limitation categories are execution_quality_spread, proxy_market_features, temporal_baseline_maturity; highest-value missing input is execution_quality_spread.

Spread-provider selection remains deferred until the operator identifies the intended execution venue.
No trade is recommended. No automatic threshold or route change is authorized.
