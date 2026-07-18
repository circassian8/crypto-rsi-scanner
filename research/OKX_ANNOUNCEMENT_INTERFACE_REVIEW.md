# OKX Announcement Interface Review

Reviewed: 2026-07-18 UTC

## Verdict

OKX's official Help Center is a promising first-party catalyst source. Its
regional announcement pages expose dated listing, delisting, trading-update,
deposit/withdrawal, and API notices. However, this review did not find a
documented announcement REST or WebSocket contract in the current official
OKX v5 API guide.

Do not invent a hidden Contentful/API endpoint, scrape a guessed regional page,
or promote Help Center HTML directly into authoritative Decision Radar evidence.
The source registry entry `okx_announcements` remains a capability placeholder,
not an implemented or authorized provider.

## Official evidence reviewed

1. The global OKX Help Center announcement category exposes current dated
   notices and explicit categories, including new listings, delistings, trading
   updates, deposit/withdrawal suspensions, API, and other notices:
   https://www.okx.com/help/category/announcements
2. The OKX US latest-announcements page demonstrates that availability and
   article coverage are regional; it exposes a smaller US-specific category and
   article set:
   https://www.okx.com/en-us/help/section/announcements-latest-announcements
3. The OKX US API-announcements Help Center section is a category of human-
   readable notices about API changes. It is not itself documentation for a
   machine-readable announcement API:
   https://www.okx.com/en-us/help/section/announcements-api
4. The current official v5 API guide documents REST and WebSocket trading and
   market-data interfaces plus regional API-domain requirements. This review
   did not find an announcement-list or announcement-stream endpoint contract
   there:
   https://www.okx.com/docs-v5/en/

Absence from the v5 guide is not proof that no separate OKX content interface
exists. It means this checkout cannot currently certify one as a supported,
stable evidence contract.

## Required boundary before implementation

- The operator must select the applicable official OKX region/domain. Results
  differ across global, US, EU, UK, and other regional Help Centers; combining
  them without a jurisdiction rule would manufacture coverage.
- OKX must document a machine interface, or the operator must separately
  approve a bounded public-page acquisition contract after reviewing applicable
  terms, robots/access policy, and retention/redistribution constraints.
- A future acquisition must be explicit-authorized, no-send, no-trade, and
  bounded to named category pages and article pages with no redirect following,
  retries, alternate hosts, proxies, VPNs, or region bypasses.
- Accepted category/article bytes must be immutable and fingerprinted. Preserve
  source URL, category, provider publication time, local read-completion time,
  article identity, pagination/coverage, regional domain, request ledger, and
  parser version.
- Missing pages, changed markup, incomplete pagination, unparseable dates, and
  unavailable regions must remain explicit coverage gaps. Zero parsed rows from
  a failed source never means no announcements.
- Asset/instrument resolution and source-independence checks remain required.
  A notice can provide catalyst or risk context, but it cannot create
  directional bias by itself.

## Consequences

- No OKX provider call, authorization, parser, transport, score, route, or
  Protocol-v2 admission is created by this review.
- Keep `okx_announcements` visible as unavailable/planned coverage rather than
  silently treating the registry name as an active provider.
- Continue using the documented Bybit v5 announcement contract as the primary
  selected-venue path, subject to its separate authorization and recorded
  regional reachability block. Never retry or bypass that block.
- Flaky news aggregation remains secondary context and cannot substitute for
  official exchange evidence.

## Revisit gate

Reopen implementation when the applicable regional source and access contract
are explicitly selected and approved. The first implementation should be an
offline parser/normalizer against operator-reviewed immutable bytes; any live
capture then needs a separate bounded authorization, request ledger, immutable
raw evidence, source coverage, health/backoff, freshness, strict doctor, and an
explicit Protocol-v2 annex decision. It remains research-only and cannot send,
trade, place orders, create paper trades, write normal RSI rows, or create Event
Alpha `TRIGGERED_FADE`.
