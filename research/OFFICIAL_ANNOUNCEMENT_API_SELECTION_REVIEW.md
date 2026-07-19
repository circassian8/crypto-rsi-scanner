# Official Announcement API Selection Review

Reviewed: 2026-07-19 UTC

## Verdict

KuCoin and Bitget both publish documented public announcement REST contracts.
They are viable first-party Catalyst Radar sources and are materially stronger
activation candidates than guessed Help Center endpoints or flaky third-party
RSS aggregation.

KuCoin was selected as the first **offline contract implementation** and Bitget
as the second. Both strict synthetic-byte contracts are fixture-verified, but a
current-documentation recheck found that KuCoin now identifies its UTA endpoint
as the replacement for the implemented v1 path. This ordering creates no
provider authorization and permits no live API call:

- KuCoin's historical v1 contract uses public/no-permission `GET
  /api/v3/announcements`, but the current official contract is `GET
  /api/ua/v1/market/announcement`. The historical fixture parser and doctor
  remain audit evidence only and are barred from live use.
- Bitget documents public `GET /api/v2/public/annoucements`—including the
  provider's exact `annoucements` spelling—with explicit categories/subtypes,
  time bounds, cursor pagination, stable IDs, publication clocks, language, and
  official URL, but only 10 rows per page.

Neither provider is active in this repository. KuCoin's current UTA contract is
not implemented; Bitget remains offline-only. Any later live capture requires a
current versioned contract, separate already-present authorization flag,
explicit confirmation, bounded request plan, immutable accepted bytes, and
strict doctor success.

## Official evidence reviewed

1. KuCoin's current UTA API documents public `GET
   https://api.kucoin.com/api/ua/v1/market/announcement`, with `language`,
   `type`, `pageNumber`, `pageSize`, `startTime`, and `endTime` request fields
   and a renamed response schema:
   https://www.kucoin.com/docs-new/rest/ua/get-announcements
2. KuCoin's official change log says the UTA endpoint replaces `GET
   /api/v3/announcements`:
   https://www.kucoin.com/docs-new/change-log
3. The historical v1 page remains the provenance for the retained fixture
   contract, not a live activation source:
   https://www.kucoin.com/docs-new/rest/spot-trading/market-data/get-announcements
4. KuCoin's official human announcement center exposes matching new-listing,
   product-update, maintenance, and delisting categories. It is useful for
   review but must not be substituted for exact API bytes:
   https://www.kucoin.com/announcement
5. Bitget's official API introduction says its developer documentation is the
   authoritative API document and links directly to its announcement API:
   https://www.bitget.com/api-doc/common/intro
6. Bitget documents `GET /api/v2/public/annoucements`, one-month coverage,
   announcement-time bounds, cursor pagination, maximum page size 10, required
   language, and listing/product/security/API/delisting/maintenance categories:
   https://www.bitget.com/api-doc/common/notice/Get-All-Notices

## Why the KuCoin v1 proof is retained but not activated

- The historical endpoint was explicitly public and no-permission in its
  versioned official contract.
- One page can request up to 50 rows, reducing the request count needed for a
  bounded observation window.
- Response-level totals/current-page/page-size make incomplete coverage
  detectable instead of silently healthy-empty.
- `annType` is an array, so one notice can retain multiple official roles
  without title-only reclassification.
- Stable `annId`, `cTime`, language, description, and official URL give the
  offline contract enough identity and clock material to fail closed.

These benefits explain the original offline ordering; they do not override the
official replacement notice. Bitget is the fixture-verified source-diverse
second official witness. Its
smaller cursor pages and deprecated `annDesc` remain separate from KuCoin's
total/page-count contract rather than being forced into one pagination model.

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

1. **Complete:** add a strict synthetic-fixture KuCoin response normalizer with
   no HTTP client, environment read, artifact write, or policy side effect.
2. **Complete:** bind exact request parameters, response code, pagination
   totals, item identity, categories, publication time, language, URL, and
   response byte digests.
3. **Complete:** reject response/code/schema extension, duplicate IDs,
   page/count drift, future or malformed clocks, unsafe URLs, unknown
   languages, oversized text, secret-like fields, and unbounded pagination.
4. **Complete:** the no-call readiness surface now reports the legacy endpoint
   as superseded, the current UTA contract as missing, zero current provider
   requests, separate authorization state, and the disable action. It has no
   HTTP client or write and cannot become ready from the legacy flag.
5. **Complete offline:** descriptor-anchored fixture mechanics seal exact
   response bytes, request ledger, normalized snapshot, fingerprints, manifest,
   and completion receipt; strict doctor re-derives the bundle and no pointer is
   published. `live_public_http` mode is explicitly rejected.
6. **Next:** implement and fixture-test the current UTA response/pagination
   contract and a matching immutable doctor. Only after that and separate
   operator authorization may a confirmed bounded live transport be considered,
   with no redirects, retries, alternate hosts, proxies, VPNs, or region bypass,
   plus health/backoff and retention review.
7. Keep every capture campaign-detached and Protocol-v2-ineligible until an
   explicit annex binds a genuine strict-clean namespace.
8. **Bitget complete offline:** preserve the exact misspelled path, optional
   type filter, required language, maximum-10 page, last-ID cursor chain,
   request/acquisition clocks, type/subtype pairs, deprecated description, and
   complete/partial semantics.
9. **Bitget readiness complete:** expose the separate authorization flag and
   exact 31-day, maximum-20-request future plan without a client or write. It
   stays blocked until immutable capture, strict doctor, and live transport are
   implemented, even when authorization is present.

## Consequences

- KuCoin's historical response and immutable-capture contracts are fixture-
  verified, superseded for live use, and not authoritative or Protocol-v2-
  admitted. The current UTA contract is not yet implemented.
- Bitget's second offline contract is implemented, but remains unconfigured,
  unauthorized, inactive, and Protocol-v2-ineligible.
- Bybit remains the selected execution venue and its documented announcement
  endpoint remains useful when permitted reachability exists. KuCoin/Bitget
  catalyst evidence cannot substitute for Bybit-native spread, depth, impact,
  intraday, or derivatives evidence.
- No provider call, credential, authorization, score, route, threshold, send,
  trade, order, paper trade, normal RSI write, or Event Alpha
  `TRIGGERED_FADE` is created by this selection.
