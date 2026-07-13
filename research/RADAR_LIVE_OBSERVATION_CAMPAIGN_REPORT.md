# Decision Radar live observation campaign

Status: **in progress — baseline warming**. Research and decision support only;
this report contains no trade recommendation.

As of 2026-07-13 15:31 UTC, two explicitly authorized CoinGecko no-send cycles
made bounded provider calls. Both calls succeeded; none failed. One additional
attempt stopped before any network call because its generated namespace did not
match the repository's lowercase namespace normalization. That naming defect is
fixed, and every future Make cycle now creates a new lowercase UTC namespace.

## Current authority

- Namespace: `radar_market_no_send_20260713t152704z`
- Run: `2026-07-13T15:27:13.330145+00:00|no_key_live`
- Operator revision: 9
- Strict doctor: `WARN`, zero blockers, one unrelated configured-but-unobserved
  CryptoPanic warning
- Dashboard: ready and verified HTTP 200 at `http://127.0.0.1:8765/`
- Pointer: published to this exact run/revision/operator-state binding
- Pilot audit contract: v1
- Market provenance: `crypto_radar_market_provenance_v2`, contract v2

The first real cycle at 15:17 UTC was a clean zero-idea market observation, but
its strict result could not become authoritative because the zero-row
CoreOpportunity writer did not materialize an empty canonical JSONL file. The
strict doctor reported no artifact blockers, publication failed closed, and the
fixture pointer was preserved. The zero-row contract is now fixed and covered by
an end-to-end strict-publication regression.

## Empirical evidence so far

- Provider calls: 2 attempted, 2 succeeded, 0 failed.
- Universe: 80 fetched and 30 retained in the authoritative cycle; 20 stable-like
  and 7 low-liquidity rows were excluded.
- History: 60 retained observations across 30 assets, exactly 2 observations per
  asset.
- Baseline: 0 cold, 30 warming, 0 warm. Warm status still requires eight prior
  observations; this campaign does not claim maturity early.
- Latest feature counts: 120 direct and 90 proxy feature values.
- Direct bases: provider-derived price sparkline returns and provider-observed
  volume/turnover.
- Proxy bases: CoinGecko 24-hour volume as a liquidity proxy and cross-sectional
  log-turnover volume z-scores.
- Spread coverage: 0 of 30. Spread is explicitly unavailable, not inferred.
- Market anomalies: 1 total.
- Decision routes: `risk_watch=1`.
- Pending outcomes: 1, matching the one current Decision idea.

The visible idea is DEXE, a market-led `risk_watch` row associated with fresh
sell-pressure evidence. It is not actionable. Its actionability/evidence/risk
scores are 42.32 / 52.45 / 48.00. The canonical soft penalties are unknown
catalyst, unavailable spread, incomplete market-led confirmation, and a temporal
baseline that is not warm. Missing information is spread, derivatives
confirmation, and a catalyst source URL.

## Safety result

Both cycles remained no-send and research-only. Telegram sends, trades, Event
Alpha paper trades, normal RSI writes, and `TRIGGERED_FADE` creations were all
zero. No threshold was lowered, no synthetic outcome or label was created, and
the dashboard remained on the previous trusted pointer until the exact live
generation passed its publication gates.

## Evidence-based next input

The highest-value missing input is **public order-book or another trusted spread
source**. Spread coverage was 0/30, and the only visible real idea was capped to
dashboard/risk review partly because execution quality could not be verified.
That is a directly observed limitation. Derivatives, DEX, and broader-universe
work should not be implemented ahead of it without contrary campaign evidence.

## Next observation

Do not run rapid duplicate cycles to manufacture warm-up. The next meaningful
observation should be no earlier than 2026-07-13 16:27 UTC, using:

```sh
make radar-market-no-send PYTHON=.venv/bin/python
```

Make generates a new immutable lowercase UTC namespace and rechecks live
authorization before the provider boundary. This report should be updated as
the bounded campaign progresses; it is not yet a final warm-baseline report.
