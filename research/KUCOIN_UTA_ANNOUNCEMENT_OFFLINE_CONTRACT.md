# KuCoin UTA Announcement Offline Contract

Status: **current endpoint response and immutable fixture capture contracts
implemented and verified; live transport not implemented** as of 2026-07-19 UTC.

## Scope

Decision Radar now has a strict offline contract for KuCoin's current public
`GET /api/ua/v1/market/announcement` endpoint. KuCoin's official change log
says this UTA endpoint replaces historical `GET /api/v3/announcements`.

Run the current fixture proof with:

```text
make radar-announcements-kucoin-uta-smoke PYTHON=.venv/bin/python
```

Run the disposable immutable-capture proof with:

```text
make radar-announcements-kucoin-uta-capture-smoke PYTHON=.venv/bin/python
```

The response adapter has no HTTP client, environment read, or persistence. The
capture module accepts supplied fixture bytes only, requires confirmation,
writes six immutable artifacts inside a disposable root, strictly re-derives
them, and retains nothing. Neither module has a live command, pointer,
notification, route, score, order, or trading path. The older v1 fixture parser
and doctor remain separately readable historical audit evidence but are barred
from live use.

## Closed current contract

- Fixed provider identity: public `https://api.kucoin.com`, exact UTA path,
  permission `NULL`, public rate-limit pool, documented request weight 20.
- Exact request keys: `language`, `type`, `pageNumber`, `pageSize`, `startTime`,
  and `endTime`; the local window is capped at 31 days.
- The requested page-size cap is a conservative local 50-row bound taken from
  the official example; it is not represented as a stronger provider promise.
- Exact response keys: `totalNumber`, `totalPage`, `pageNumber`, `pageSize`, and
  `list`; item keys are `id`, `title`, `type`, `description`, `releaseTime`,
  `language`, and `url`.
- Contiguous page prefixes, totals, response page size, row counts, and the
  20-request / 1,000-row local bounds must reconcile. Partial remains partial;
  healthy-empty requires complete zero-row pagination.
- The projection retains the SHA-256 of each exact UTA response body, its local
  acquisition clock, lineage ID, stable provider ID, categories, release clock,
  language, description-summary status, and official URL.
- Duplicate JSON keys, schema extensions, pagination drift, duplicate IDs,
  unknown categories, malformed/future clocks, unsafe URLs, and unbounded data
  fail closed.
- `releaseTime` is provider publication time, not the trading, funding,
  maintenance, or other event time. No direction is inferred.

## Current boundary

Readiness now distinguishes three facts:

1. the current UTA response contract is fixture-verified;
2. the current UTA immutable fixture capture/doctor is fixture-verified; and
3. live transport is not implemented or authorized.

An ambient authorization flag cannot unlock a call. The next safe command is
the offline UTA capture smoke. A later change may consider separately authorized,
explicitly confirmed transport only after bounded request, health/backoff, and
retention review. Genuine bytes would still need the same strict doctor and a
separate annex decision before any policy use.

No current or historical KuCoin fixture is attached to Event Alpha discovery,
Decision candidates, campaign/dashboard authority, or Protocol v2.

Official sources:

- https://www.kucoin.com/docs-new/rest/ua/get-announcements
- https://www.kucoin.com/docs-new/change-log
