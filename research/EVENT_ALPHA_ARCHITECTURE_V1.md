# Event Alpha Architecture V1

Event Alpha remains a research-only catalyst radar. The consolidation package
layout gives new code a home while old import paths continue to work.

## Package Map

- `crypto_rsi_scanner/event_alpha/providers/`: Event Alpha provider
  activation, readiness, preflight, provider-health, official-exchange,
  CryptoPanic, source-registry, and source-pack orchestration.
- `crypto_rsi_scanner/event_alpha/radar/`: integrated radar, market state and
  reaction logic, market anomaly scanning, source coverage, core opportunity
  aggregation/store views, evidence acquisition, opportunity verdicts, impact
  hypotheses, and incident artifacts.
- `crypto_rsi_scanner/event_alpha/artifacts/`: artifact context, portable
  path helpers, run-ledger rows, retention, locks, and schema v1.
- `crypto_rsi_scanner/event_alpha/notifications/`: notification preview,
  no-send delivery, send-readiness, go/no-go, inbox, pack, SLO, pause,
  Telegram final-check, recipient-check, sender, and formatting helpers.
- `crypto_rsi_scanner/event_alpha/outcomes/`: integrated outcomes,
  calibration, feedback readiness/eval export, burn-in, quality review,
  signal-quality, priors, and policy simulation.
- `crypto_rsi_scanner/event_alpha/doctor/`: schema doctor, check registry, and
  compatibility doctor layers.
- `crypto_rsi_scanner/event_alpha/namespace/`: namespace status and lifecycle
  reporting.
- `crypto_rsi_scanner/cli/`: CLI facade, parser snapshots, and command-group
  extraction targets.

`crypto_rsi_scanner/event_alpha/MODULE_MAP.md` lists old top-level module paths
and their intended package locations.

## V1 Boundary Rules

These rules are the anti-sprawl contract for future Codex/Claude passes:

- Old import shims remain during the v1 migration so historical imports,
  tests, and Make targets keep working.
- New code should import the new package paths listed in the package map.
- Old top-level `crypto_rsi_scanner/event_*.py` shim modules should not gain
  new implementation logic. They may re-export symbols, hold compatibility
  comments, or contain temporary glue only when a tested migration requires it.
- CLI parser construction belongs in `crypto_rsi_scanner/cli/parser.py`.
- CLI dispatch belongs in `crypto_rsi_scanner/cli/dispatch.py`.
- Command groups belong in `crypto_rsi_scanner/cli/commands_*.py`.
- New tests belong in `tests/event_alpha/`, `tests/rsi/`, or `tests/cli/`.
- `tests/test_indicators.py` is a compatibility umbrella runner, not the home
  for new behavior tests.
- New artifact fields require a schema v1 update before or with writer changes.
- New doctor checks require a check-registry entry with schema dependencies.
- Every new namespace needs lifecycle status, retention policy, and explicit
  `safe_for_send_readiness`.

## Safety Invariants

- Research-only/no-trading/no-paper/no-send guards apply to every Event Alpha
  path unless a later explicit human decision says otherwise.
- No live trading, paper trading, execution, order logic, or normal RSI signal
  writes.
- Event Alpha does not create `TRIGGERED_FADE`; that remains owned by
  `event_fade.py` plus proxy-fade eligibility.
- Provider calls and Telegram sends stay opt-in and guarded; tests and CI run
  no live provider calls and no live Telegram sends by default.
- Tests and smokes require no API keys and must not print secrets.
- Long/fade language is research-only operator review language.

## Artifact Flow

Provider/preflight artifacts feed source coverage and integrated radar sidecars.
Integrated radar writes candidates, CoreOpportunity rows, cards, previews,
daily briefs, outcomes, and calibration/performance artifacts under a namespace.
The artifact doctor is schema-first: it inspects namespace lifecycle state,
validates schema v1 structure, runs schema safety checks, then runs legacy and
consistency checks. Doctor checks that depend on fields must declare schema
dependencies in the check registry.

Artifact implementation code now lives in package modules:

- `event_alpha.artifacts.context` for namespace/path context and row filtering.
- `event_alpha.artifacts.paths` for portable operator path labels and absolute
  path scrubbing.
- `event_alpha.artifacts.run_ledger` for Event Alpha run ledger rows.
- `event_alpha.artifacts.retention` for dry-run/confirmed artifact pruning.
- `event_alpha.artifacts.locks` for profile/namespace run locks.
- `event_alpha.namespace.status` for stale/deprecated namespace markers.

The top-level imports remain compatibility shims with no runtime deprecation
warnings. Artifact paths and output schemas must stay unchanged unless a
separate migration explicitly updates schema v1 consumers.

## Radar Implementation Move

Radar/core implementation code now lives in package modules:

- `event_alpha.radar.integrated_radar` for integrated radar orchestration.
- `event_alpha.radar.market_state` and `event_alpha.radar.market_reaction` for
  market snapshots, opportunity lanes, and reaction classification.
- `event_alpha.radar.market_anomaly_scanner` for broad market anomaly seeds and
  catalyst-search queue artifacts.
- `event_alpha.radar.core_opportunities` and
  `event_alpha.radar.core_opportunity_store` for canonical operator-facing
  opportunity rows and read-side views.
- `event_alpha.radar.evidence_acquisition` for source-pack search result
  acquisition and reconciliation.
- `event_alpha.radar.source_coverage` for provider/source-pack readiness and
  coverage dashboards.
- `event_alpha.radar.opportunity_verdict` for final research opportunity
  verdict policy.
- `event_alpha.radar.impact_hypotheses` and
  `event_alpha.radar.impact_hypothesis_store` for impact-hypothesis generation
  and artifact persistence.
- `event_alpha.radar.incidents` for profile-scoped incident artifacts.

The old top-level modules remain quiet compatibility shims. After the radar
move, the size gate was `125` top-level `event_*.py` files, `18`
compatibility shims, and `107` remaining top-level implementation files.

## Provider Implementation Move

Event Alpha provider/readiness orchestration code now lives in package modules:

- `event_alpha.providers.live_provider_readiness` for no-call provider
  activation readiness.
- `event_alpha.providers.coinalyze_preflight` for Coinalyze preflight and
  bounded no-send rehearsal artifacts.
- `event_alpha.providers.official_exchange` and
  `event_alpha.providers.official_exchange_activation` for official exchange
  artifact normalization and activation rows.
- `event_alpha.providers.cryptopanic` for CryptoPanic operational preflight
  helpers.
- `event_alpha.providers.provider_health` for Event Alpha provider health and
  circuit-breaker state.
- `event_alpha.providers.source_registry` and
  `event_alpha.providers.source_packs` for source semantics and playbook source
  packs.
- `event_alpha.providers.bybit_announcements_preflight`,
  `event_alpha.providers.unlock_calendar_preflight`, and
  `event_alpha.providers.dex_onchain_readiness` for fixture-first provider
  activation/readiness scaffolds.

The lower-level reusable provider adapter packages remain in place:
`crypto_rsi_scanner/event_providers/`, `crypto_rsi_scanner/derivatives_providers/`,
and `crypto_rsi_scanner/supply_providers/` are not folded into Event Alpha.
Current size gate after this provider move: `125` top-level `event_*.py` files,
`29` compatibility shims, and `96` remaining top-level implementation files.

## Notification Implementation Move

Event Alpha notification, preview, delivery, send-readiness, and
Telegram-formatting code now lives in package modules:

- `event_alpha.notifications.pipeline` for notification planning, preview
  rendering, heartbeat copy, research-review/exploratory/core digest rendering,
  and guarded send orchestration.
- `event_alpha.notifications.delivery` for the no-send/delivery ledger and
  explicit `status`/`status_detail` rows.
- `event_alpha.notifications.sender` for structured Telegram send-attempt
  metadata and safe error redaction.
- `event_alpha.notifications.runs` for notification-run summary artifacts.
- `event_alpha.notifications.go_no_go`,
  `event_alpha.notifications.readiness`, and
  `event_alpha.notifications.final_check` for operator readiness and final
  no-send checks.
- `event_alpha.notifications.checklist`, `inbox`, `pack`, `pause`, and `slo`
  for day-1 operator review, export, pause state, and SLO reports.
- `event_alpha.notifications.formatting` as the public formatting facade for
  Telegram digest/heartbeat/preview helpers and chunk sizing.
- `event_alpha.notifications.recipient_check` for guarded Telegram recipient
  diagnostics.

The old top-level modules remain quiet compatibility shims. No-send semantics,
structured skip telemetry, delivery `status`/`status_detail` fields, and normal
heartbeat wording (`Strict alerts`, `Research candidates`, `Raw source
candidates`) remain behavior-freeze gates. Current size gate after this
notification move: `125` top-level `event_*.py` files, `42` compatibility shims,
and `83` remaining top-level implementation files.

## Outcomes Implementation Move

Event Alpha outcome, calibration, feedback, burn-in, quality, priors, and
policy-simulation code now lives in package modules:

- `event_alpha.outcomes.integrated_radar_outcomes` for integrated radar outcome
  fill, outcome reports, calibration reports, and cross-run performance
  dashboards.
- `event_alpha.outcomes.calibration` for artifact-backed calibration reports and
  recommendation-only calibration priors.
- `event_alpha.outcomes.feedback` for feedback-readiness checks and proposed
  eval-case exports from feedback/missed artifacts.
- `event_alpha.outcomes.burn_in` for burn-in scorecards, burn-in readiness, and
  burn-in export packs.
- `event_alpha.outcomes.quality` for quality review, quality coverage,
  signal-quality fixture evals, signal-quality export, and tuning worksheets.
- `event_alpha.outcomes.priors` for opt-in calibration-prior loading, shadow
  comparison, and guarded score adjustment.
- `event_alpha.outcomes.policy_simulator` for offline policy-threshold
  simulation over local artifacts.

The old top-level modules remain quiet compatibility shims. Output artifact
paths and schemas remain unchanged, and outcome terminology such as
`validation_rate`, `validated`, `invalidated/noise`, and `inconclusive` remains
research-only review language. Current size gate after this outcomes move:
`125` top-level `event_*.py` files, `56` compatibility shims, and `69`
remaining top-level implementation files.

## Future Code Placement

New Event Alpha code should land in the subpackage first. Keep a top-level shim
when an old import path is public or used by Make targets. Move physical code in
small, tested slices only.

## How To Add A Provider

1. Put Event Alpha activation/preflight orchestration in
   `event_alpha/providers/`; keep reusable HTTP/parser adapters in
   `event_providers/`, `derivatives_providers/`, or `supply_providers/`.
2. Add fixture/parser status first. Live calls must be blocked by default and
   require an explicit allow flag, bounded request budget, redacted request
   ledger, and no-send mode.
3. Add source-registry/source-pack metadata and provider-health keys.
4. Write provider preflight/rehearsal artifacts with `research_only=true`,
   no-send side-effect counters, and schema ids when known.
5. Add source coverage, artifact doctor, and fixture tests proving no live
   calls, no sends, no trades, no paper trades, no RSI rows, no
   `TRIGGERED_FADE`, and no secrets.

## How To Add A Radar Artifact

1. Define the row contract in `event_alpha/artifacts/schema_v1.py`.
2. Write artifacts under the active namespace through artifact path/context
   helpers, using relative operator paths.
3. Attach canonical identity, source lineage, safety counters, freshness, and
   schema metadata when applicable.
4. Add integrated-radar/source-coverage/card/doctor checks if the artifact feeds
   operator surfaces.
5. Add tests in `tests/event_alpha/`; do not add the new behavior to the
   umbrella runner directly.

## How To Add A Notification Lane

1. Put planning/rendering logic in `event_alpha/notifications/pipeline.py` or a
   focused notification package module.
2. Preserve no-send rehearsal behavior and delivery rows with
   `status`/`status_detail`.
3. Keep Telegram delivery guarded by `RSI_EVENT_ALERTS_ENABLED=1`, explicit send
   commands, and final readiness checks.
4. Preserve research-only copy and "Not a trade signal" framing where operator
   messages can be mistaken for action instructions.
5. Add preview, delivery, final-check, inbox/SLO, and artifact-doctor tests.

## How To Add An Outcome Or Calibration Field

1. Add the field to schema v1 and the relevant outcome/calibration row writer.
2. Keep terminology research-only: `validated`, `invalidated`, `noise`,
   `inconclusive`, `validation_rate`, and recommendation-only prior language.
3. New prior/threshold suggestions must include `auto_apply=false` and
   low-sample warnings where applicable.
4. Update cards/daily brief/report rendering only after the schema and doctor
   dependencies are declared.
5. Add outcome/calibration tests in `tests/event_alpha/`.

## CLI Split Direction

`scanner.py` is now a compatibility wrapper for the package CLI entrypoint.
`crypto_rsi_scanner.cli.parser.build_parser()` owns argparse construction
without calling `parse_args()` or any command branch, and
`crypto_rsi_scanner.cli.dispatch.dispatch_args()` routes parsed args into
command-group modules. The current command modules still bind to historical
scanner helpers for command bodies; future slices can move one body at a time
behind the same parser, dispatch, and Make target coverage.

Compatibility rules for CLI refactors:

- `python3 -m crypto_rsi_scanner.scanner --help` must keep working.
- `python3 -m crypto_rsi_scanner.cli.main --help` must expose the same operator
  flags.
- Existing flags, defaults, Make targets, and old imports must remain
  compatible until a migration is explicit.
- Parser snapshot tests must cover representative RSI, paper, maintenance,
  Event Alpha radar, doctor, notification, provider readiness, Coinalyze, and
  official-exchange paths before parser changes land.
- Dispatch tests must cover representative Event Alpha, provider readiness,
  notification preview, export, and default RSI scan routes before moving
  command bodies out of scanner helpers.
