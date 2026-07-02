# Event Alpha Architecture V1

Event Alpha remains a research-only catalyst radar. The consolidation package
layout gives new code a home while old import paths continue to work.

## Package Map

- `crypto_rsi_scanner/event_alpha/providers/`: provider activation,
  readiness, preflight, and source-pack wrappers.
- `crypto_rsi_scanner/event_alpha/radar/`: integrated radar, market state and
  reaction logic, market anomaly scanning, source coverage, core opportunity
  aggregation/store views, evidence acquisition, opportunity verdicts, impact
  hypotheses, and incident artifacts.
- `crypto_rsi_scanner/event_alpha/artifacts/`: artifact context, portable
  path helpers, run-ledger rows, retention, locks, and schema v1.
- `crypto_rsi_scanner/event_alpha/notifications/`: no-send delivery and sender
  wrappers.
- `crypto_rsi_scanner/event_alpha/outcomes/`: integrated outcomes and
  calibration wrappers.
- `crypto_rsi_scanner/event_alpha/doctor/`: schema doctor, check registry, and
  compatibility doctor layers.
- `crypto_rsi_scanner/event_alpha/namespace/`: namespace status and lifecycle
  reporting.
- `crypto_rsi_scanner/cli/`: CLI facade, parser snapshots, and command-group
  extraction targets.

`crypto_rsi_scanner/event_alpha/MODULE_MAP.md` lists old top-level module paths
and their intended package locations.

## Safety Invariants

- No live trading, paper trading, execution, order logic, or normal RSI signal
  writes.
- Event Alpha does not create `TRIGGERED_FADE`; that remains owned by
  `event_fade.py` plus proxy-fade eligibility.
- Provider calls and Telegram sends stay opt-in and guarded.
- Tests and smokes require no API keys and must not print secrets.
- Long/fade language is research-only operator review language.

## Artifact Flow

Provider/preflight artifacts feed source coverage and integrated radar sidecars.
Integrated radar writes candidates, CoreOpportunity rows, cards, previews,
daily briefs, outcomes, and calibration/performance artifacts under a namespace.
The artifact doctor first validates schema v1 structure, then runs higher-order
safety, delivery, source coverage, provider readiness, outcome, and namespace
checks.

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

The old top-level modules remain quiet compatibility shims. Current size gate
after this pass: `125` top-level `event_*.py` files, `18` compatibility shims,
and `107` remaining top-level implementation files. The moved radar targets
are all shims at the top level. `event_source_packs.py` remains provider-side
per `crypto_rsi_scanner/event_alpha/MODULE_MAP.md`.

## Future Code Placement

New Event Alpha code should land in the subpackage first. Keep a top-level shim
when an old import path is public or used by Make targets. Move physical code in
small, tested slices only.

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
