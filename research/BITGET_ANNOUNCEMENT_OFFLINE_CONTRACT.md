# Bitget Announcement Offline Contract

Status: implemented and fixture-verified on 2026-07-19 UTC.

## Scope

The repository has a strict offline parser for Bitget's documented public
announcement endpoint:

```text
GET https://api.bitget.com/api/v2/public/annoucements
```

The provider's `annoucements` path spelling is preserved exactly. Run the
synthetic-byte proof with:

```text
make radar-announcements-bitget-smoke PYTHON=.venv/bin/python
```

It performs no provider call, environment read, artifact write, notification,
routing, scoring, order, or trade.

## Closed contract

- The request binds a maximum 31-day publication-time window, required
  `en_US`, optional documented announcement type, and a 1–10 row limit.
- Pagination begins without a cursor. Every later cursor must equal the final
  `annId` from the preceding full page. A short or empty final page proves
  complete coverage; a full final page remains partial with its next cursor.
- A failed/truncated prefix never means no announcements. Healthy-empty
  requires one complete empty first page.
- The exact response schema requires `code=00000`, `msg=success`, provider
  request time, and documented item fields. Duplicate JSON keys, schema drift,
  cursor breaks, nonterminal short pages, duplicate IDs, bad clocks, unsafe
  URLs, and unknown type/subtype pairs fail closed.
- Provider request time must be within 60 seconds of local body-read completion.
  Exact response SHA-256, acquisition time, request lineage, cursor, and row
  count survive projection.
- `annDesc` is explicitly deprecated and is never treated as a complete article.
- `cTime` is provider publication time. It is not trading, funding, maintenance,
  effective-event, or first-market-reaction time.
- Listing, delisting, maintenance, product, security, API, and news roles remain
  distinct. No title inference reclassifies them.

## Authority state

The contract is synthetic, unconfigured, unauthorized, inactive, and detached
from discovery, campaign, dashboard, scores, routes, and Protocol v2. It has no
directional authority and creates no sends, trades, orders, paper trades,
normal RSI writes, or Event Alpha `TRIGGERED_FADE`.

A later live boundary requires separate operator authorization and confirmation,
no-redirect/no-retry bounded transport, immutable accepted bytes, request
ledger, health/backoff, strict doctor, retention review, source-independence
assessment, and explicit Protocol-v2 annex selection.

Official contract reviewed:
https://www.bitget.com/api-doc/common/notice/Get-All-Notices
