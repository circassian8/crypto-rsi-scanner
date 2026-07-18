# Coinbase Listing Interface Review

Reviewed: 2026-07-18 UTC

## Verdict

Coinbase exposes two useful but non-interchangeable first-party surfaces:

1. Its current listing-process guide directs readers to `@CoinbaseMarkets` on
   X for new-asset and process updates.
2. Its documented public Exchange market-data API exposes current products,
   product status, restriction flags, and auction state.

The first is an official announcement channel but this project has no approved
X transport. The second is a documented machine contract, but it proves only
what the exchange product state showed when the system observed it. It cannot
be relabeled as a prior listing decision or publication timestamp.

Keep `coinbase` and `coinbase_announcements` as planned/unimplemented source
capabilities. Do not scrape X, infer an announcement from API discovery, or use
Coinbase product state as Bybit execution-quality evidence.

## Official evidence reviewed

1. Coinbase's current centralized-exchange listing guide describes phased
   market launch and directs users to `@CoinbaseMarkets` on X for new-asset and
   process updates:
   https://www.coinbase.com/blog/a-guide-to-the-digital-asset-listing-process-at-coinbase
2. Coinbase Exchange's official introduction states that its market-data APIs
   are public and subject to the Exchange Market Data Terms of Use:
   https://docs.cdp.coinbase.com/exchange/introduction/welcome
3. The documented public `GET /products` endpoint returns available currency
   pairs and explicit product state such as stable product ID, `status`,
   `trading_disabled`, `cancel_only`, `post_only`, `limit_only`, and
   `auction_mode`. Coinbase notes that fields other than product ID may change:
   https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-all-known-trading-pairs
4. The documented public WebSocket `status` channel periodically sends all
   products/currencies, while the auction channel exposes current auction
   state and indicative—not firm—quotes:
   https://docs.cdp.coinbase.com/exchange/websocket-feed/channels

## Closed source roles

### Official announcement role

- Only a message from the official listing-update channel, acquired under a
  reviewed supported transport, can claim a Coinbase listing announcement.
- An X post needs exact post identity, author/account identity, publication and
  local acquisition clocks, immutable accepted bytes/payload, edit/delete
  handling, request ledger, source URL, and access/retention terms.
- This repository has no such transport or authorization today. A browser page,
  search result, embed, mirror, screenshot, or third-party repost is not an
  authoritative machine source.

### Observed product-state role

- One immutable `GET /products` capture may prove current Coinbase product
  identity and trading/auction restrictions at its local read-completion time.
- A newly seen product or changed status is a point-in-time exchange-state
  transition only. Without a prior complete snapshot it is merely current
  state, not a new listing event.
- The first locally observed product time is not Coinbase's announcement time,
  approval time, integration start, or trading-launch time. Do not backfill any
  of those clocks.
- `auction_mode` and restriction flags describe launch/trading context. They do
  not imply direction, healthy liquidity, or executable spread/depth.
- Coinbase state may later corroborate cross-venue listing/tradability context,
  but Bybit USDT-linear perpetuals remain the selected Protocol-v2 execution
  surface. Coinbase cannot substitute for Bybit-native instrument, spread,
  depth, impact, intraday, or derivatives evidence.

## Required boundary before implementation

- Select separately whether the desired input is announcement evidence,
  observed product-state evidence, or both. Never merge their clocks or claims.
- An announcement path needs an official supported X/API transport plus
  explicit provider authorization and applicable access/retention review.
- A product-state path may use only the documented public Exchange contract,
  under a separately present authorization flag despite public/no-key access.
- Start with offline normalizers against synthetic or operator-reviewed bytes.
  Fixtures prove parsing only and never become live authority.
- A live product capture should use one bounded complete catalog request, no
  redirects/retries/alternate hosts, immutable accepted bytes, local request
  start/read-completion clocks, response headers needed for contract review,
  exact product identity/status projection, prior-snapshot binding for any
  transition claim, health/backoff, freshness, strict doctor, and explicit
  annex selection.
- Missing products, failed/incomplete catalogs, and unavailable channels remain
  coverage gaps. Absence from one regional/product surface does not prove a
  universal delisting.

## Consequences

- No Coinbase provider call, X access, credential, authorization, parser,
  transport, score, route, threshold, evidence authority, or Protocol-v2
  admission is created by this review.
- Keep official Coinbase announcement evidence unavailable until a supported
  transport is approved.
- Treat the public Exchange API as a possible later cross-venue state witness,
  never as an announcement feed or selected-venue execution substitute.

## Revisit gate

Reopen when the operator explicitly selects an announcement and/or product-
state lane and the matching access/retention contract. Any implementation
remains research-only, separately authorized, bounded, immutable, no-send, and
annex-detached by default. It cannot send, trade, place orders, create paper
trades, write normal RSI rows, or create Event Alpha `TRIGGERED_FADE`.
