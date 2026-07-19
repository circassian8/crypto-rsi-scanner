# Official Announcement API Selection Review

Reviewed: 2026-07-19 UTC

## Verdict

KuCoin and Bitget both publish documented public announcement REST contracts.
They are viable first-party Catalyst Radar sources and are materially stronger
activation candidates than guessed Help Center endpoints or flaky third-party
RSS aggregation.

Select KuCoin as the next **offline contract implementation** and keep Bitget as
the second implementation candidate. This ordering creates no provider
authorization and permits no live call:

- KuCoin documents a public/no-permission `GET /api/v3/announcements` endpoint,
  explicit page/count fields, up to 50 requested rows, stable announcement IDs,
  types, publication clocks, language, description, and official URL.
- Bitget documents public `GET /api/v2/public/annoucements`—including the
  provider's exact `annoucements` spelling—with explicit categories/subtypes,
  time bounds, cursor pagination, stable IDs, publication clocks, language, and
  official URL, but only 10 rows per page.

Neither endpoint is active in this repository. Implement parsing and closed
coverage semantics offline first. Any later live capture requires a separate
already-present authorization flag, explicit confirmation, a bounded request
plan, immutable accepted bytes, and strict doctor success.

## Official evidence reviewed

1. KuCoin's current official API documents `GET
   https://api.kucoin.com/api/v3/announcements` as public, permission `NULL`,
   public rate-limit pool, request weight 20, and a latest-news interface whose
   default search is within one month. Its example exposes `totalNum`,
   `totalPage`, `currentPage`, `pageSize`, `annId`, `annTitle`, `annType`,
   `annDesc`, `cTime`, `language`, and `annUrl`:
   https://www.kucoin.com/docs-new/rest/spot-trading/market-data/get-announcements
2. KuCoin's official human announcement center exposes matching new-listing,
   product-update, maintenance, and delisting categories. It is useful for
   review but must not be substituted for exact API bytes:
   https://www.kucoin.com/announcement
3. Bitget's official API introduction says its developer documentation is the
   authoritative API document and links directly to its announcement API:
   https://www.bitget.com/api-doc/common/intro
4. Bitget documents `GET /api/v2/public/annoucements`, one-month coverage,
   announcement-time bounds, cursor pagination, maximum page size 10, required
   language, and listing/product/security/API/delisting/maintenance categories:
   https://www.bitget.com/api-doc/common/notice/Get-All-Notices

## Why KuCoin is first

- The endpoint is explicitly public and no-permission in the official contract.
- One page can request up to 50 rows, reducing the request count needed for a
  bounded observation window.
- Response-level totals/current-page/page-size make incomplete coverage
  detectable instead of silently healthy-empty.
- `annType` is an array, so one notice can retain multiple official roles
  without title-only reclassification.
- Stable `annId`, `cTime`, language, description, and official URL give the
  offline contract enough identity and clock material to fail closed.

Bitget remains valuable as a source-diverse second official witness. Its
smaller cursor pages and deprecated `annDesc` make it a better second contract
after the shared identity, coverage, and clock rules are proven on KuCoin.

## Closed evidence semantics

- `cTime` is provider publication/creation time. It is not automatically a
  trading-start, funding-open, maintenance-start, or event time.
- An explicit event time in a title/description remains separately parsed
  evidence with its own certainty. If it is absent or ambiguous, retain unknown.
- API description text may be truncated or deprecated. It cannot be presented
  as a complete article body or used to invent missing terms.
- Listing, delisting, maintenance, product-update, security, and promotional
  categories remain distinct. Promotions do not become listings because an
  asset symbol appears.
- Exact provider ID, announcement ID, category/type, language, source URL,
  provider publication time, local request/read-completion clocks, request
  identity, page/total coverage, raw-byte digest, and parser version must
  survive projection.
- Zero accepted rows is healthy-empty only when the exact requested window and
  pagination coverage are complete. Failed, truncated, rate-limited, or partial
  acquisition never means no announcements.
- Asset/instrument resolution and source-independence checks remain required.
  A first-party exchange notice may provide catalyst or risk context, but it
  cannot create directional bias by itself.

## Implementation boundary

1. Add a strict synthetic-fixture KuCoin response normalizer with no HTTP
   client, environment read, artifact write, or policy side effect.
2. Bind exact request parameters, response code, pagination totals, item
   identity, categories, publication time, language, URL, and explicit units.
3. Reject response/code/schema extension, duplicate IDs, page/count drift,
   future or malformed clocks, unsafe URLs, unknown languages, oversized text,
   secret-like fields, and unbounded pagination.
4. Add a no-call readiness surface that reports configuration, separate
   authorization, maximum requests, expected provider activity, rollback, and
   exact next command.
5. Only after separate operator authorization, add a confirmed bounded capture
   with no redirects, retries, alternate hosts, proxies, VPNs, or region bypass.
6. Persist immutable accepted bytes, request ledger, coverage, fingerprints,
   completion receipt, health/backoff, and strict-doctor truth. Keep it
   campaign-detached and Protocol-v2-ineligible until the annex binds it.

## Consequences

- KuCoin is selected only as the next offline official-announcement contract;
  it is not live-enabled, authoritative, or Protocol-v2-admitted.
- Bitget remains planned as the second documented official API candidate.
- Bybit remains the selected execution venue and its documented announcement
  endpoint remains useful when permitted reachability exists. KuCoin/Bitget
  catalyst evidence cannot substitute for Bybit-native spread, depth, impact,
  intraday, or derivatives evidence.
- No provider call, credential, authorization, score, route, threshold, send,
  trade, order, paper trade, normal RSI write, or Event Alpha
  `TRIGGERED_FADE` is created by this selection.
