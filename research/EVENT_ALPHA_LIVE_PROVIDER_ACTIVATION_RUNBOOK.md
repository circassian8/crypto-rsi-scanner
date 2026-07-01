# Event Alpha Live Provider Activation Runbook

Event Alpha live-provider activation is a no-call, no-send readiness workflow
until a human explicitly promotes a provider. The readiness report is meant to
answer three questions before any live provider is enabled:

- Which source packs are blocked by missing provider configuration?
- Which fixture or smoke artifacts already prove the parser and source-pack
  contract?
- What bounded no-send rehearsal should run next?

This workflow is research-only. It must not send Telegram, trade, paper trade,
write normal RSI signal rows, execute orders, print secrets, or create
`TRIGGERED_FADE`.

## Readiness First

Run the no-call readiness report before enabling a provider:

```bash
make event-alpha-live-provider-readiness PROFILE=notify_llm_deep PYTHON=python3
```

For fixture proof without network calls or keys:

```bash
make event-alpha-live-provider-readiness-smoke PYTHON=python3
```

The report writes:

- `event_live_provider_activation_readiness.json`
- `event_live_provider_activation_readiness.md`

The JSON/Markdown should include `live_calls_allowed=false`, provider fixture
availability, sidecar/smoke targets, activation phase, request caps, budget
fields, request-ledger requirements, provider health key, source-pack impacts,
and the source packs or research lanes that remain blocked without market or
provider confirmation.

## Provider Activation Order

Use the readiness report and source coverage together. The default activation
priority is:

1. Coinalyze derivatives, OI, funding, liquidations.
2. Official exchange announcements from Bybit/Binance public or fixture paths.
3. Structured unlock/calendar evidence such as Tokenomist or Messari.
4. DEX/on-chain/protocol metrics from GeckoTerminal or DefiLlama-style sources.
5. Context/news sources such as CryptoPanic, RSS, and GDELT.

Binance public or fixture announcement normalization is separate from the
signed Binance listener. Public/fixture announcement parsing can be
`fixture_ready` without Binance credentials. The signed listener remains
blocked until its API key/secret and bounded no-send rehearsal are configured.

## No-Send Rehearsal

After readiness is clean, run a no-send rehearsal for the target namespace:

```bash
make event-alpha-notify-llm-deep-real-no-send-rehearsal PYTHON=python3
make event-alpha-send-readiness PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-artifact-doctor PROFILE=notify_llm_deep_rehearsal STRICT=1 PYTHON=python3
make event-alpha-notification-inbox PROFILE=notify_llm_deep_rehearsal PYTHON=python3
make event-alpha-daily-brief PROFILE=notify_llm_deep_rehearsal PYTHON=python3
```

Do not enable sends until the no-send rehearsal preview, source coverage,
artifact doctor, inbox, and send-readiness agree on the same core ids, lanes,
blocked reasons, and provider status.

## Stale Namespaces

If an old namespace is known to contain pre-policy artifacts, mark it stale
instead of letting it confuse current send-readiness:

```bash
make event-alpha-mark-namespace-stale \
  ARTIFACT_NAMESPACE=notify_llm_deep \
  SUPERSEDED_BY=notify_llm_deep_rehearsal \
  REASON='superseded by canonical no-send rehearsal'
```

Strict artifact doctor skips stale namespaces by default and reports the stale
marker. To inspect them deliberately, pass `--event-alpha-include-stale-artifacts`
through the CLI or use a direct diagnostic command.

Before deleting or archiving anything, run the dry-run plan:

```bash
make event-alpha-prune-or-archive-stale-namespace ARTIFACT_NAMESPACE=notify_llm_deep
```

This target reports a plan only. It does not remove artifacts.

## Export Hygiene

For Pro-model handoff, use:

```bash
make export-src-with-artifacts PYTHON=python3
```

The exporter overwrites `crypto_rsi_scanner_source_with_artifacts.zip`, excludes
secrets and machine-local noise, and normalizes future-dated mtimes so extracted
archives do not produce clock-skew warnings.
