# Kraken Listing Interface Review

Reviewed: 2026-07-19 UTC

## Verdict

Kraken exposes three useful but non-interchangeable first-party catalyst
surfaces:

1. Its official listing roadmap shows assets that passed Kraken's Listing
   Committee and are planned for integration.
2. Kraken Blog asset-listing posts can state that funding or trading is live.
3. Kraken Support publishes human-readable delisting, migration, suspension,
   fork, and asset-support notices.

The roadmap is pre-launch context, not proof of a completed listing or current
tradability. Kraken explicitly says roadmap inclusion is not a guarantee and
that funding/trading remain unsupported until an official announcement. The
official pages reviewed here did not expose a documented stable announcement
REST, WebSocket, RSS, or other machine contract.

Keep `kraken_announcements` planned, unimplemented, unconfigured, and
unauthorized. Do not infer a trading launch from roadmap discovery, scrape an
undocumented page or feed, or use Kraken state as Bybit execution evidence.

## Official evidence reviewed

1. Kraken's official listing roadmap identifies planned token, chain, and
   network integrations, but says inclusion is not a guarantee and directs
   users to its official listings channel for the eventual announcement:
   https://www.kraken.com/listings
2. Kraken's official explanation calls the roadmap a source of truth for assets
   that passed its committee and are planned for listing, while again separating
   roadmap inclusion from funding/trading availability:
   https://blog.kraken.com/product/accelerating-new-listings-at-kraken
3. Kraken Blog publishes dated asset-listing articles that can explicitly state
   when trading is live. These are human-readable first-party pages, not a
   documented machine announcement contract:
   https://blog.kraken.com/product/asset-listings/asset-is-available-for-trading
4. Kraken Support maintains a dated delistings section with scheduled removals,
   regional restrictions, migrations, and pair-removal notices:
   https://support.kraken.com/sections/delistings
5. Kraken's official fork/airdrop/migration policy says relevant updates are
   communicated through email, its blog, and its social channel. This review
   found no supported project transport that turns those channels into an
   immutable machine source:
   https://support.kraken.com/articles/115013895208-general-statement-on-forks-airdrops-and-addition-of-new-cryptocurrencies

Absence of a machine contract from this bounded review does not prove that
Kraken will never publish one. It means the current checkout cannot certify a
stable automated acquisition interface today.

## Closed source roles

### Listing-roadmap role

- A roadmap observation may provide planned-listing or scheduled-risk context
  only.
- Preserve exact asset, chain/network, roadmap category, source URL, first local
  observation time, and immutable source bytes if a future access contract is
  approved.
- First local observation is not committee-decision time, announcement time,
  funding-open time, or trading-start time.
- Roadmap presence alone cannot create directional bias, strict catalyst
  eligibility, tradability, spread, or actionability.

### Trading-launch announcement role

- Only an exact official launch statement acquired under an approved supported
  transport may claim that Kraken funding or trading became available.
- Preserve page/post identity, provider publication time, stated launch time,
  local request/read-completion clocks, corrections, regional availability,
  immutable accepted bytes, source URL, and asset/instrument identity.
- A search result, mirror, third-party repost, screenshot, or inferred product
  appearance is not the authoritative publication.

### Delisting and operational-risk role

- Official support notices may provide delisting, migration, suspension, and
  regional-risk context after exact source and clock validation.
- A regional notice is not universal. Missing or unavailable regional coverage
  never means an asset is globally unaffected.
- These notices can raise risk, shorten expiry, or block tradability; they do
  not manufacture directional confidence.

## Required boundary before implementation

- The operator must select roadmap context, launch announcements, operational-
  risk notices, or an explicit combination. Their identities and clocks must
  remain separate.
- Kraken must document a machine interface, or the operator must explicitly
  approve a bounded official-page/local-import contract after applicable access,
  robots, terms, retention, and redistribution review.
- Any live acquisition remains separately authorization-gated, no-send,
  no-trade, no-redirect, no-retry, and bounded to named first-party surfaces.
  No proxy, VPN, alternate host, or regional bypass is allowed.
- Begin with a closed offline normalizer against operator-reviewed immutable
  bytes. Fixtures prove parsing only and never become live authority.
- A future capture must retain exact accepted bytes, request ledger, coverage,
  pagination, publication/stated-event/local clocks, regional source identity,
  health/backoff, fingerprints, strict doctor, and explicit Protocol-v2 annex
  selection.
- Missing pages, changed markup, incomplete coverage, unparseable clocks, and
  unavailable regions remain explicit gaps. Zero rows from a failed source
  never means no events.

## Consequences

- No Kraken provider call, X/social access, authorization, parser, transport,
  score, route, threshold, evidence authority, or Protocol-v2 admission is
  created by this review.
- Kraken roadmap information may become useful context after a separately
  approved capture contract, but it cannot substitute for an actual launch
  announcement.
- Bybit USDT-linear perpetuals remain the selected execution surface. Kraken
  cannot substitute for Bybit-native instrument, spread, depth, impact,
  intraday, or derivatives evidence.
- Flaky news aggregation remains secondary and cannot replace exact official
  Kraken evidence.

## Revisit gate

Reopen when the operator selects exact source roles and approves either a
documented machine interface or a bounded first-party page/local-import
contract. Any implementation remains research-only, separately authorized,
immutable, campaign-detached, and Protocol-v2-ineligible until its exact capture
identity is sealed in the annex. It cannot send, trade, place orders, create
paper trades, write normal RSI rows, or create Event Alpha `TRIGGERED_FADE`.
