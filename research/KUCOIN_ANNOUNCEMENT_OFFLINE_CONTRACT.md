# KuCoin Announcement Offline Contract

Status: implemented and fixture-verified on 2026-07-19 UTC.

## Scope

The repository now has a strict offline contract for KuCoin's documented
public `GET /api/v3/announcements` response. It is an input-contract proof, not
a live provider activation.

The implementation validates synthetic bytes only and performs no HTTP call,
environment lookup, artifact write, notification, routing, scoring, order, or
trade. Run it with:

```text
make radar-announcements-kucoin-smoke PYTHON=.venv/bin/python
```

The separate observational readiness surface is:

```text
make radar-announcements-kucoin-readiness PYTHON=.venv/bin/python
```

It reads only whether the dedicated KuCoin authorization flag is already
present and reports an exact trailing-24-hour request plan, a 20-request upper
bound, expected future activity, and the disable action. It performs no call or
write and remains blocked even when authorization is present because immutable
capture and strict doctor are not implemented.

## Closed contract

- The request identity binds `currentPage`, requested `pageSize`, `annType`,
  `lang`, `startTime`, and `endTime`; the time window is bounded to 31 days.
- The response code must be the exact string `200000` and each response object,
  data object, and announcement item must match the documented field set.
- Accepted pages are exact contiguous prefixes beginning at page 1, with a
  maximum of 20 responses and 1,000 rows. Total, page count, current page,
  response page size, and row counts must reconcile.
- The provider may return a smaller page size than requested; both values stay
  explicit and the reported page size controls pagination reconciliation.
- Complete coverage and partial coverage remain distinct. Zero rows are
  healthy-empty only after complete pagination.
- Exact response SHA-256, local acquisition time, request lineage, stable
  `annId`, official `annType` values, `cTime`, language, description summary,
  and official URL survive projection.
- Duplicate JSON keys, IDs, categories, pages, unsafe URLs, schema extensions,
  oversized text, malformed or future clocks, pagination drift, and rows
  outside the requested window fail closed.
- `cTime` is publication time, not funding, trading, maintenance, or event
  time. The normalized event time remains unknown.
- `annDesc` is labeled a provider summary rather than a complete article body.
- Official categories are retained as supplied. Promotions and maintenance do
  not become listings through title inference.

## Authority state

The contract remains:

- unconfigured and unauthorized;
- detached from Event Alpha discovery, Decision routes, scores, campaign
  authority, dashboard authority, and Protocol v2;
- context-only and without directional authority;
- research-only, with zero sends, trades, orders, paper trades, normal RSI
  writes, or Event Alpha `TRIGGERED_FADE` creation.

The no-call readiness surface is now implemented. A later live boundary still
requires separately present operator authorization, explicit confirmation,
bounded no-redirect and no-retry acquisition, immutable accepted bytes, request
ledger, health/backoff, completion receipt, strict doctor, retention review,
and explicit Protocol-v2 annex selection.

Official contract reviewed:
https://www.kucoin.com/docs-new/rest/spot-trading/market-data/get-announcements
