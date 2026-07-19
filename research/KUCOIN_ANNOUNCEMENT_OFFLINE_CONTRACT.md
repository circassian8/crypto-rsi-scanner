# KuCoin Announcement Offline Contract

Status: **historical v1 contract, fixture-verified, and explicitly ineligible for
live use** as of 2026-07-19 UTC.

## Scope

The repository has a strict offline contract for KuCoin's legacy public `GET
/api/v3/announcements` response. KuCoin's current change log and Unified
Trading Account documentation say that `GET /api/ua/v1/market/announcement`
replaces this endpoint. The v1 implementation therefore remains a historical
input-contract proof and may not be used as a live provider path.

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
present. It reports the current UTA endpoint as not implemented, labels the
legacy v1 plan historical and non-executable, sets the current request bound to
zero, and recommends no provider action. It performs no call or write and
remains blocked even when authorization is present.

Immutable capture mechanics can be proven offline with:

```text
make radar-announcements-kucoin-capture-smoke PYTHON=.venv/bin/python
```

The smoke seals exact synthetic response bytes, a non-secret request ledger,
normalized snapshot, manifest, and completion receipt in one disposable
temporary root; strict doctor then re-derives every byte before the root is
removed. It publishes no pointer. The capture API accepts only explicit
`offline_fixture` mode today and rejects `live_public_http`, so synthetic bytes
cannot be relabeled as genuine evidence.

## Closed historical v1 contract

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

- superseded for live use, unconfigured, and unauthorized;
- detached from Event Alpha discovery, Decision routes, scores, campaign
  authority, dashboard authority, and Protocol v2;
- context-only and without directional authority;
- research-only, with zero sends, trades, orders, paper trades, normal RSI
  writes, or Event Alpha `TRIGGERED_FADE` creation.

The legacy no-call readiness, immutable bundle, and strict-doctor mechanics are
implemented offline only. Before any live boundary, a new version must close
the current UTA request/response/pagination contract and its own immutable
doctor. Only then could separately present operator authorization, explicit
confirmation, bounded no-redirect/no-retry transport, health/backoff, retention
review, and Protocol-v2 annex selection be considered.

Official current contract and migration evidence reviewed:

- https://www.kucoin.com/docs-new/rest/ua/get-announcements
- https://www.kucoin.com/docs-new/change-log

Historical v1 contract retained for audit:
https://www.kucoin.com/docs-new/rest/spot-trading/market-data/get-announcements
