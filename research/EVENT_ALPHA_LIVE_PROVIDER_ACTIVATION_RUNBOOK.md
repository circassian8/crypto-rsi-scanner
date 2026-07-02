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

## Coinalyze Derivatives Preflight

Coinalyze is the first derivatives/OI/funding activation lane. Start with the
provider-specific no-call preflight:

```bash
make event-alpha-coinalyze-preflight PROFILE=notify_llm_deep PYTHON=python3
```

The Make target defaults to the clean `coinalyze_preflight` namespace. If an
operator explicitly points it at a stale namespace such as `notify_llm_deep`,
the command must block with `blocked_stale_namespace` unless
`ALLOW_STALE_NAMESPACE_WRITE=1` is deliberately supplied for a diagnostic run.

For fixture proof without a key or network:

```bash
make event-alpha-coinalyze-preflight-smoke PYTHON=python3
```

The preflight writes:

- `event_coinalyze_preflight.json`
- `event_coinalyze_preflight.md`

The report may mention only the required environment variable name,
`RSI_EVENT_DISCOVERY_COINALYZE_API_KEY`. It must not print a key value. Normal
preflight reports `missing_config` when the key is absent. If a key is present,
live calls are still blocked unless an operator explicitly passes the live
preflight flag through the CLI after reviewing quota and doctor output.

The guarded no-send rehearsal is:

```bash
make event-alpha-coinalyze-no-send-rehearsal PROFILE=notify_llm_deep PYTHON=python3
```

The Make target defaults to the clean `coinalyze_no_send_rehearsal` namespace.

Current guard behavior:

- no key: exits gracefully with `missing_config`
- key configured but no explicit live flag: `live_call_blocked_by_default`
- explicit stale namespace: `blocked_stale_namespace` unless
  `ALLOW_STALE_NAMESPACE_WRITE=1`
- live-capable rehearsal: requires a key, explicit allow flag, no-send mode,
  writable request ledger, and the configured request budget
- no Telegram sends, trades, paper trades, normal RSI rows, or
  Event Alpha-created `TRIGGERED_FADE`

A bounded live rehearsal is intentionally small:

```bash
ALLOW_LIVE_PREFLIGHT=1 \
  make event-alpha-coinalyze-no-send-rehearsal \
  PROFILE=notify_llm_deep \
  ARTIFACT_NAMESPACE=coinalyze_no_send_rehearsal \
  PYTHON=python3
```

By default it requests only BTC/ETH/SOL-sized coverage and honors the
Coinalyze preflight request budget. To rehearse a different tiny symbol set,
set `RSI_EVENT_ALPHA_COINALYZE_PREFLIGHT_SYMBOLS` before the command and keep
the budget small.

Expected artifacts after a bounded live rehearsal:

- `event_coinalyze_request_ledger.jsonl`
- `event_derivatives_state.jsonl`
- `event_derivatives_crowding_candidates.jsonl`
- `event_fade_short_review_candidates.jsonl`
- `event_coinalyze_rehearsal_report.json`
- `event_coinalyze_rehearsal_report.md`

Abort if the request ledger is missing, provider health is in backoff, a secret
value appears in artifacts, live calls happen without the explicit flag, or
artifact doctor reports blockers. Source coverage and the daily brief should
link Coinalyze preflight/rehearsal artifacts only when those files exist; a
missing linked artifact is a doctor issue.

## Provider Activation Order

Use the readiness report and source coverage together. The default activation
priority is:

1. Coinalyze derivatives, OI, funding, liquidations.
2. Official exchange announcements from Bybit/Binance public or fixture paths.
3. Structured unlock/calendar evidence such as Tokenomist or Messari.
4. DEX/on-chain/protocol metrics from GeckoTerminal or DefiLlama-style sources.
5. Context/news sources such as CryptoPanic, RSS, and GDELT.

Official exchange is the next provider family to activate, but it remains
fixture/no-call until it has its own provider-specific preflight, redacted
request ledger, small-budget no-send rehearsal, provider-health update, and
artifact-doctor checks. Binance public or fixture announcement normalization is
separate from the signed Binance listener. Public/fixture announcement parsing
can be `fixture_ready` without Binance credentials. The signed listener remains
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

Known pre-canonical namespaces can be marked idempotently:

```bash
make event-alpha-mark-known-stale-namespaces PYTHON=python3
```

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

## Artifact-Backed Preview Refresh

When the artifacts already exist and the operator only needs a fresh preview or
delivery-row skip telemetry, regenerate it without live providers or sends:

```bash
make event-alpha-notify-preview-from-artifacts \
  PROFILE=notify_llm_deep \
  ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal \
  PYTHON=python3
```

The resulting `research_review_digest` delivery rows should include rendered,
eligible, and skipped counts, skipped reason counts, skipped family summaries,
rendered alert/core ids, and a `preview_only` marker in the preview body.
