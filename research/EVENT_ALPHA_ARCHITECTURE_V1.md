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
  path helpers, run-ledger rows, retention, locks, and the schema v1 facade.
- `crypto_rsi_scanner/event_alpha/artifacts/schema/`: schema v1 package
  surfaces for base registry objects, shared fields, validators, core
  opportunities, integrated candidates, deliveries, source coverage, provider
  readiness/preflight, derivatives, market rows, official exchange, scheduled
  catalysts/unlocks, outcomes, calibration, namespace, and run-ledger rows.
- `crypto_rsi_scanner/event_alpha/notifications/`: notification preview,
  no-send delivery, send-readiness, go/no-go, inbox, pack, SLO, pause,
  Telegram final-check, recipient-check, sender, and formatting helpers.
- `crypto_rsi_scanner/event_alpha/outcomes/`: integrated outcomes,
  calibration, feedback readiness/eval export, burn-in, quality review,
  signal-quality, priors, and policy simulation.
- `crypto_rsi_scanner/event_alpha/doctor/`: schema doctor, check registry,
  plugin check modules, report sections, namespace/safety/consistency phases,
  and the public artifact-doctor orchestrator.
- `crypto_rsi_scanner/event_alpha/namespace/`: namespace status and lifecycle
  reporting.
- `crypto_rsi_scanner/event_alpha/config/`: Event Alpha profiles, preflight,
  scheduler, v1 readiness, and health-guard configuration helpers.
- `crypto_rsi_scanner/event_alpha/radar/llm/`: Event Alpha LLM budget and
  catalyst-frame evaluation helpers that remain research-only inputs to
  deterministic radar gates.
- `crypto_rsi_scanner/event_core/`: shared event-research infrastructure used
  by Event Alpha and lower-level providers. `clock.py` owns deterministic
  research-clock helpers; `models.py` owns small shared event dataclasses.
- `crypto_rsi_scanner/cli/`: CLI facade, parser snapshots, and command-group
  extraction targets. `cli/services/event_alpha.py` is now a compatibility
  aggregator over focused Event Alpha service modules such as
  `event_alpha_notifications.py`, `event_alpha_integrated.py`,
  `event_alpha_outcomes.py`, `event_alpha_reports.py`,
  `event_alpha_provider_preflights.py`, `event_alpha_namespace.py`,
  `event_alpha_research.py`, and `event_alpha_fade_review.py`.
  `cli/services/scanner_api.py` is now a compatibility aggregator over
  focused modules in `cli/services/scanner_parts/`; new command logic should move into
  focused `cli/services/` or `cli/commands_*.py` modules instead.
- `crypto_rsi_scanner/storage_parts/`: shared SQLite storage mixins for
  connection setup, schema text, additive migrations, scan/signal/outcome rows,
  previous-flag/alert/subscriber/meta state, paper-trade rows, and scan-status
  maintenance. `crypto_rsi_scanner/storage.py` remains the public `Storage`
  facade.
- `crypto_rsi_scanner/backtest_parts/`: RSI backtest package surfaces for CLI,
  engine, results, costs, risk/membership, reports, and data helpers.
  `crypto_rsi_scanner/backtest.py` remains the historical CLI/helper facade
  over the canonical backtest API.

`crypto_rsi_scanner/event_alpha/MODULE_MAP.md` records the current package map
and the fact that no old flat Event Alpha public compatibility shims remain.

## V1 Boundary Rules

These rules are the anti-sprawl contract for future Codex/Claude passes:

- No old flat Event Alpha public compatibility shims remain. Deleted old imports
  are tombstoned and allowed to fail, with the manifest in
  `research/EVENT_ALPHA_DELETED_SHIMS.md/json`.
- Docs should show canonical package paths, and tombstone tests cover deleted
  old import failure in `tests/event_alpha/test_no_old_event_alpha_imports.py`.
- New code should import the new package paths listed in the package map.
- No old top-level `crypto_rsi_scanner/event_*.py` Event Alpha shim modules
  remain. Future work must not recreate them except through an explicit public
  compatibility decision. Temporary glue, re-export-only modules, and old-path
  comments belong in tombstone reports, not in production packages.
- Migration-era implementation filenames are not part of the final
  architecture. Run `make architecture-transitional-file-check`,
  `make architecture-naming-check`, `make architecture-size-gates`, and
  `make architecture-final-report` after moving code. Removed old target aliases
  are not part of the current runbook surface.
- Remaining `legacy` wording is allowed only for historical artifact row
  semantics, generated compatibility report fields, old CLI aliases, tombstone
  records, or historical decision/log entries. New user-facing flags should use
  the historical-artifact wording, while parser support for old aliases remains
  compatibility-only.
- `crypto_rsi_scanner.event_alpha.shims` is the tombstone and deleted-path audit
  registry. It emits shim, dependency, and old-import reports with zero active
  flat Event Alpha shims. Artifact doctor warns if a deleted old shim path is
  reintroduced.
- CLI parser construction belongs in `crypto_rsi_scanner/cli/parser.py`.
  `build_parser()` is an orchestrator over `parser_base.py`,
  `parser_event_alpha.py`, `parser_notifications.py`,
  `parser_provider_readiness.py`, `parser_integrated_radar.py`,
  `parser_rsi.py`, `parser_backtest.py`, `parser_paper.py`,
  `parser_export.py`, and `parser_maintenance.py`.
- CLI dispatch belongs in `crypto_rsi_scanner/cli/dispatch.py`.
- Command groups belong in `crypto_rsi_scanner/cli/commands_*.py`.
- Event Alpha command metadata belongs in
  `crypto_rsi_scanner/cli/event_alpha_command_registry.py`; registry rows must
  keep no-send/no-live-provider defaults explicit.
- New tests belong in `tests/event_alpha/`, `tests/rsi/`, or `tests/cli/`.
- `tests/test_indicators.py` is a compatibility umbrella runner, not the home
  for new behavior tests.
- New artifact fields require a schema v1 update before or with writer changes.
- Schema implementation belongs in `event_alpha/artifacts/schema/`; the
  historical `event_alpha/artifacts/schema_v1.py` module is a compatibility
  aggregator.
- New doctor checks require a check-registry entry with schema dependencies.
- Every new namespace needs lifecycle status, retention policy, and explicit
  `safe_for_send_readiness`.
- Shared storage and backtest changes must keep the `storage.py` and
  `backtest.py` facades import-compatible. New implementation should land under
  `storage_parts/` or `backtest_parts/` unless a later behavior-freeze pass
  explicitly changes those contracts.
- Progressive size gates are static-only: `make architecture-size-gates` warns for
  violations already in `research/ARCHITECTURE_SIZE_BASELINE.json` and blocks newly
  introduced file/function/class/module ownership violations.

## Safety Invariants

- Research-only/no-trading/no-paper/no-send guards apply to every Event Alpha
  path unless a later explicit human decision says otherwise.
- No live trading, paper trading, execution, order logic, or normal RSI signal
  writes.
- Event Alpha does not create `TRIGGERED_FADE`; that remains owned by
  `event_fade.py` plus proxy-fade eligibility.
- Event Alpha may write `FADE_SHORT_REVIEW` research candidates for manual
  crowding/exhaustion review, but those rows are not `TRIGGERED_FADE` and must
  not become triggers without deterministic `event_fade.py` + `proxy_fade`
  output.
- `event_fade.py` is intentionally outside the Event Alpha package during v1.
  Future refactors must not move it under Event Alpha unless a new explicit
  decision preserves the deterministic `TRIGGERED_FADE` ownership boundary.
- `event_clock.py` and `event_models.py` were shared event infrastructure, not
  Event Alpha-specific implementation. Their implementations now live under
  neutral `crypto_rsi_scanner/event_core/` modules; old flat Event Alpha import
  paths are tombstoned rather than retained as shims.
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

The public artifact doctor entrypoint is intentionally small:
`event_alpha.doctor.artifact_doctor` re-exports compatibility helpers and routes
`diagnose_artifacts()` through `execution.py` plus `context.py`, `discovery.py`,
and `aggregation.py`. Report rendering enters through
`doctor/report_sections/summary.py`, with focused section modules available for
future migrations. The behavior-compatible core is preserved as
`event_alpha.doctor.artifact_doctor_core` until each remaining check can move
behind fixture-backed plugin tests without changing strict/WARN semantics.

Artifact implementation code now lives in package modules:

- `event_alpha.artifacts.context` for namespace/path context and row filtering.
- `event_alpha.artifacts.paths` for portable operator path labels and absolute
  path scrubbing.
- `event_alpha.artifacts.run_ledger` for Event Alpha run ledger rows.
- `event_alpha.artifacts.retention` for dry-run/confirmed artifact pruning.
- `event_alpha.artifacts.locks` for profile/namespace run locks.
- `event_alpha.namespace.status` for stale/deprecated namespace markers.

No retained top-level artifact import shims remain. Deleted old imports are
allowed to fail; artifact paths and output schemas must stay unchanged unless a
separate migration explicitly updates schema v1 consumers.

## Internal Large-Module Split

The largest Event Alpha internal modules have small public wrappers and
behavior-compatible canonical cores. New code should use the focused module
homes and should not recreate migration-era wrappers:

- `event_alpha.notifications.pipeline` is the public notification orchestrator.
  Models, selection, preview writing, delivery writing, message rendering,
  heartbeat wording, skip telemetry, plan building, and safety helpers have
  focused modules under `event_alpha.notifications/`. The core implementation
  module is `event_alpha.notifications.pipeline_core`.
- `event_alpha.artifacts.research_cards` is now a package. Models, renderer,
  index, lineage, and card section modules live under
  `event_alpha.artifacts.research_cards/`; the public API module is
  `event_alpha.artifacts.research_cards.api`.
- `event_alpha.artifacts.daily_brief` is now a package. Builder, context,
  models, renderer, and daily-brief section modules live under
  `event_alpha.artifacts.daily_brief/`; the public API module is
  `event_alpha.artifacts.daily_brief.api`.
- `event_alpha.radar.integrated_radar` is the public integrated-radar wrapper.
  Cycle, inputs, sidecars, merge, family, policy, artifact writer, report, and
  manifest homes live under `event_alpha.radar.integrated/`; the public API
  module is `event_alpha.radar.integrated.api`.
- `event_alpha.radar.impact_hypotheses` is now a package. Models, rules,
  builder, store, report, inbox, scoring, and lineage homes live under
  `event_alpha.radar.impact_hypotheses/`; the public API module is
  `event_alpha.radar.impact_hypotheses.api`.
- `event_alpha.radar.core_opportunity_store` is the public store wrapper.
  Core models, store operations, serialization, aggregation, merge, card links,
  and validators live under `event_alpha.radar.core/`; the store API module
  is `event_alpha.radar.core.store_api`.
- `event_alpha.radar.evidence_acquisition` is the public evidence wrapper.
  Evidence models, planner, executor, validators, scoring, providers, report,
  and serialization homes live under `event_alpha.radar.evidence/`; the
  acquisition API module is `event_alpha.radar.evidence.acquisition_api`.
- Medium radar packages now follow the same ownership pattern:
  `event_alpha.radar.validation/` owns validation models, review, sample, and
  report helpers; `event_alpha.radar.discovery/` owns discovery models, manual
  execution, loaders, provider composition, and reports;
  `event_alpha.radar.watchlist/` owns watchlist models, entry builders, market
  helpers, enrichment helpers, and reports; and
  `event_alpha.radar.near_miss/` owns near-miss models, refresh, candidate
  selection, and reports. Package `api.py` modules expose the stable public
  surface without migration-era legacy filenames.

This split is behavior-preserving. It does not change artifact schemas, card
copy, daily-brief grouping, notification delivery rows, source/provider
guardrails, or any research-only safety invariant.

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

The old radar top-level modules have been deleted after canonical imports,
Makefile references, docs, and compatibility assumptions moved to package
paths. Their deleted imports are tombstones and are allowed to fail.

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
The medium provider adapters also use package ownership:
`event_providers/cryptopanic/` owns the CryptoPanic provider/client/parser/
request-ledger surfaces, `derivatives_providers/coinalyze/` owns the Coinalyze
provider/client/parser surfaces, and official announcement adapters live under
`event_providers/bybit_announcements/` and
`event_providers/binance_announcements/`. Event Alpha provider-health wrappers
live under `event_alpha.providers.health/` with
`event_alpha.providers.provider_health` kept as the public package import.
Current final-retirement gate: only `crypto_rsi_scanner/event_fade.py` remains
as a top-level event module, retained public shims are zero, and old flat Event
Alpha imports are tombstoned.

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

The old notification top-level modules have been deleted after canonical
imports, Makefile references, docs, and compatibility assumptions moved to
package paths. No-send semantics, structured skip telemetry, delivery
`status`/`status_detail` fields, and normal heartbeat wording (`Strict alerts`,
`Research candidates`, `Raw source candidates`) remain behavior-freeze gates.

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

The old outcomes top-level modules have been deleted after canonical imports,
Makefile references, docs, and compatibility assumptions moved to package
paths. Output artifact paths and schemas remain unchanged, and outcome
terminology such as `validation_rate`, `validated`, `invalidated/noise`, and
`inconclusive` remains research-only review language.

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

1. Define the row contract in `event_alpha/artifacts/schema/` and keep
   `event_alpha/artifacts/schema_v1.py` compatibility exports intact.
2. Write artifacts under the active namespace through artifact path/context
   helpers, using relative operator paths.
3. Attach canonical identity, source lineage, safety counters, freshness, and
   schema metadata when applicable.
4. Add integrated-radar/source-coverage/card/doctor checks if the artifact feeds
   operator surfaces.
5. Add tests in `tests/event_alpha/`; do not add the new behavior to the
   umbrella runner directly.

## How To Add A Notification Lane

1. Put planning/rendering logic in focused notification package modules such as
   `plan_builder.py`, `message_rendering.py`, `preview_writer.py`,
   `delivery_writer.py`, or `candidate_selection.py`; keep
   `event_alpha/notifications/pipeline.py` as the public orchestrator.
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

`scanner.py` is now a small compatibility facade for the package CLI entrypoint
and old helper imports. The historical command implementation has moved to
`crypto_rsi_scanner.cli.services.scanner_api` as a measured transitional
core, not as a new home for feature work.
`crypto_rsi_scanner.cli.parser.build_parser()` owns argparse construction
without calling `parse_args()` or any command branch, and
`crypto_rsi_scanner.cli.dispatch.dispatch_args()` routes parsed args into
command-group modules. Event Alpha command bodies are split into focused
`crypto_rsi_scanner.cli.services.event_alpha_*` service modules while the old
`event_alpha.py` service module re-exports them. The remaining centralized
service refresh helpers preserve monkeypatch compatibility until direct imports
can replace them behind command-specific parity tests.

`research/CLI_FLAG_SNAPSHOT.json` is the checked-in flag/default/destination
snapshot for parser refactors. Any parser split must preserve this behavior
unless a migration is explicit.

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
  command families out of `scanner_api.py`.
