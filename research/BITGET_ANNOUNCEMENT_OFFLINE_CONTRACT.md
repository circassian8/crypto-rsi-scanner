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

The observational readiness surface is:

```text
make radar-announcements-bitget-readiness PYTHON=.venv/bin/python
```

It reads only the already-present dedicated
`RSI_DECISION_RADAR_BITGET_ANNOUNCEMENTS_LIVE` flag and reports an exact 31-day
request plan capped at 20 cursor pages / 200 rows. It never calls the provider,
writes an artifact, or creates authorization. It remains blocked even when the
flag exists because live transport is not implemented. Its current safe next
command is the disposable capture smoke; the disable action is `unset
RSI_DECISION_RADAR_BITGET_ANNOUNCEMENTS_LIVE`.

Immutable capture mechanics can be proven offline with:

```text
make radar-announcements-bitget-capture-smoke PYTHON=.venv/bin/python
```

The smoke seals exact synthetic response bytes, canonical cursor-bearing
request URLs, non-secret request/response clocks, a request ledger, normalized
snapshot, manifest, and completion receipt in one disposable temporary root.
Strict doctor re-derives every byte before that root is removed. It publishes
no pointer. The capture API accepts only explicit `offline_fixture` mode and
rejects `live_public_http`, so synthetic bytes cannot be relabeled as genuine
evidence.

## Closed contract

- The request binds a maximum 31-day publication-time window, required
  `en_US`, optional documented announcement type, and a 1–10 row limit.
- Pagination begins without a cursor. Every later cursor must equal the final
  `annId` from the preceding nonempty page. The official contract does not say
  that a short nonempty page is terminal, so stopping on any nonempty page is
  partial and exposes its final `annId` as the next cursor. Only an explicit
  empty cursor response proves complete coverage.
- A failed/truncated prefix never means no announcements. Healthy-empty
  requires one complete empty first page.
- The exact response schema requires `code=00000`, `msg=success`, provider
  request time, and documented item fields. Duplicate JSON keys, schema drift,
  cursor breaks, pages after an explicit empty response, duplicate IDs, bad
  clocks, unsafe URLs, and unknown type/subtype pairs fail closed. Short
  nonempty pages may be followed and never prove completion by themselves.
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

The no-call readiness, immutable bundle, and strict-doctor mechanics are now
implemented offline. A later live boundary still requires separate operator
authorization and confirmation, no-redirect/no-retry bounded transport,
health/backoff, retention review, source-independence assessment, and explicit
Protocol-v2 annex selection.

Official contract reviewed:
https://www.bitget.com/api-doc/common/notice/Get-All-Notices
