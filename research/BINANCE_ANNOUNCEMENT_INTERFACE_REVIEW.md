# Binance Announcement Interface Review

Reviewed: 2026-07-18 UTC

## Verdict

The repository's signed Binance CMS WebSocket path remains a legacy,
unverified research adapter. Do not activate it, extend it as an authoritative
capture surface, or include it in Protocol-v2 evidence until the exact current
Binance interface contract and applicable access terms are available from an
official source and reviewed.

This is not a claim that Binance has no announcement product. Binance's current
Developer Center advertises an Announcements product, but the current public
API catalog does not expose an Announcements API entry, endpoint definition,
message schema, authentication contract, rate limit, or terms for the
repository's `wss://api.binance.com/sapi/wss` /
`com_announcement_en` combination.

## Official evidence reviewed

1. Binance's current developer introduction says interfaces documented in its
   portal are the officially documented developer interfaces and says
   undocumented behavior should not be relied on in production because it may
   change without notice:
   https://developers.binance.com/en/docs/introduction
2. The current public API catalog lists the supported Spot, derivatives,
   wallet, institutional, investment, and Web3 API families, but no
   Announcements API entry is exposed there:
   https://developers.binance.com/en/docs/catalog
3. The Binance Developer Center advertises “Announcements — Get the latest
   Binance announcements in real-time,” which suggests a product may exist
   behind a separate enrollment or documentation surface. The public page did
   not expose enough endpoint or terms detail to validate this repository's
   legacy transport:
   https://developers.binance.com/

## Consequences

- Preserve the existing fixture parser and legacy signed-listener code for
  historical compatibility and offline regression coverage.
- Keep the signed listener disabled. Credentials plus the old live flag are not
  sufficient evidence that its current provider contract is supported.
- Do not spend more implementation effort on immutable raw-frame publication or
  Protocol-v2 integration for this path yet.
- Do not treat a legacy frame as authoritative catalyst evidence merely because
  it parses.
- Continue prioritizing the documented Bybit v5 announcement endpoint for the
  selected Bybit venue, subject to existing explicit authorization and the
  recorded regional reachability block. Never retry or bypass that block.
- Context/news aggregation remains secondary and cannot substitute for a
  documented official-exchange contract.

## Revisit gate

Reopen this source only when the operator can provide or access current official
Binance documentation that identifies the exact announcement endpoint/stream,
topic, authentication and permission model, payload schema, rate/request
limits, retention/redistribution terms, and supported environment. A later
implementation still needs a separate bounded no-send readiness/rehearsal,
redacted request ledger, immutable accepted-frame evidence, strict doctor, and
explicit provider authorization. It remains research-only and cannot send,
trade, place orders, create paper trades, write normal RSI rows, or create Event
Alpha `TRIGGERED_FADE`.
