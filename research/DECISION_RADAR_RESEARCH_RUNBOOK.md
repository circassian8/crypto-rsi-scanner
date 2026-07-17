# Decision Radar Research Runbook

Operational guide for the offline Decision Radar Empirical Validation and
Calibration Lab v1. The laboratory measures the existing canonical Decision
Model v2; it does not create another model, route taxonomy, execution system, or
production authority.

## Safety and authority boundary

Every command in this runbook is research-only and no-send. Historical replay
and report generation make zero provider calls and cannot create, inspect,
persist, or change provider authorization. They cannot mutate the authoritative
dashboard pointer, production thresholds or routes, notifications, trades,
orders, Event Alpha paper trades, normal RSI rows, or `TRIGGERED_FADE`.

Research output always has `research_only=true` and `auto_apply=false`. A shadow
recommendation is decision support only. Any production-policy change requires
a separate explicit human decision, a versioned contract, and rollback criteria.

## Frozen protocol

Always validate the checked-in protocol before running replay:

```sh
make radar-research-protocol-check PYTHON=.venv/bin/python
```

The current frozen contract is:

- protocol: `decision_radar_empirical_validation_v1`;
- frozen at: `2026-07-16T05:30:00Z`, before final-test evaluation;
- SHA-256: `efee20ccaa3dda03c8e1172633d92d6a9bf8cb3ae12c926471f2151941d5f158`;
- observation clock: completed Binance daily candle close;
- point-in-time universe: trailing 30-day quote-volume rank inside the retained
  local historical candidate pool;
- primary outcome: three days;
- sensitivity outcomes: one, seven, and fourteen days;
- fixed-start episode window: 24 hours, inclusive end;
- deterministic seed: `20260716`.

The chronological partitions are immutable for protocol v1:

| Partition | Idea start | Idea end | Outcome end | May select policy? |
|---|---|---|---|---|
| development | `2021-06-12T00:00:00Z` | `2023-01-01T00:00:00Z` | `2023-01-15T00:00:00Z` | yes |
| validation | `2023-01-15T00:00:00Z` | `2025-01-01T00:00:00Z` | `2025-01-15T00:00:00Z` | yes |
| final test | `2025-01-15T00:00:00Z` | `2026-06-01T00:00:00Z` | `2026-06-18T00:00:00Z` | no |

Fourteen-day outcome-only embargoes separate the idea windows. Do not move a
boundary, change the primary outcome, redefine a missed move, or alter the
shadow recommendation rule after looking at final-test evidence. A new design
requires a new protocol version frozen before its own holdout is opened.

## Protocol-v2 pre-registration readiness

Protocol v1 cannot answer the product's intraday, execution-quality, or
non-market evidence questions. The static Protocol-v2 requirements contract is
therefore frozen separately from any executable protocol:

```sh
make radar-research-protocol-v2-readiness PYTHON=.venv/bin/python
make radar-research-protocol-v2-check PYTHON=.venv/bin/python
```

The current readiness digest is
`683f03fe74306a80acaebf2556e2652cc67e9c725d97deb6dd083b3b28109603`.
It requires point-in-time 1h/4h market observations, exact idea/review latency,
observed venue spread/depth, catalyst timing, official calendar events,
derivatives, on-chain, and Wilder-RSI context with immutable lineage. Missing
required evidence remains unavailable; proxies and retrospective invention are
forbidden.

This is deliberately not an executable frozen protocol. Activation remains
blocked until one exact human-approved annex seals the venue and eligible
instruments, data sources, development/validation/untouched-holdout partitions,
outcomes, observed/assumed costs, point-in-time universe, unchanged route
definitions and code digest, episode handling, and minimum samples. The
Protocol-v2 holdout is undefined and unopened, its access count is zero, and no
replay, selection, or final-test target exists. Protocol-v1 final-test evidence
must never be reused to tune v2.

The execution-quality decision remains human-owned. Start with:

```sh
make radar-execution-quality-readiness PYTHON=.venv/bin/python
```

Complete the rendered template with an intended venue, `spot`/`perpetual`/`dex`
mode, quote currency, exact bounded eligible-instrument set, dated
jurisdiction/account eligibility confirmation, and the expected public/private
market-data boundary. This grants no provider, private-data, order, or trading
permission and does not select a spread provider. The concise option comparison
is [Decision Radar execution-venue decision package](DECISION_RADAR_EXECUTION_VENUE_DECISION_PACKAGE.md).
Its multiple-venue research alternative keeps every venue's book and quote
separate; it cannot close the primary cost model until one execution surface is
sealed.

## Inputs and default paths

The Make targets use these defaults:

| Purpose | Path |
|---|---|
| fixture smoke input | `fixtures/backtest_smoke/klines` |
| historical OHLCV input | `backtest_cache/binance_klines` |
| immutable research runs | `event_fade_cache/decision_radar_research_lab/runs` |
| optional feedback ledger | `event_fade_cache/decision_radar_research_lab/empirical_review_feedback.jsonl` |
| published report bundle | `research/` |
| separate live campaign projection | `research/RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT.json` |

Historical replay is point-in-time only inside the retained candidate pool. It
has residual delisting survivorship and is not a complete historical listing
master. Historical spread, order-book quality, intraday path ordering, market
cap, derivatives, calendar, catalyst, and on-chain context remain unavailable
or missing unless an exact time-valid source is supplied. Never substitute
current metadata, a fixture, or an unlabeled proxy.

## Replay modes

### Fixture smoke

Use the three-asset fixture to prove mechanics, canonical projection, episodes,
outcomes, persistence, and safety. Fixture rows are never evidence of forward
value and never enter the live campaign.

```sh
make radar-replay-smoke PYTHON=.venv/bin/python
```

### Medium replay

Use the top-30 point-in-time universe for a bounded development/validation
integration run. This mode is useful for performance and report-shape checks,
but it cannot authorize final-test access.

```sh
make radar-replay-medium PYTHON=.venv/bin/python
```

### Full selection replay

Use the top-100 point-in-time universe across development and validation. A
complete immutable full run creates the only recommendation seal that may open
the protocol-v1 final-test lane.

```sh
make radar-replay-full PYTHON=.venv/bin/python
```

Record the printed `run_fingerprint` and `run_dir`. Do not select a run by
directory recency. Medium, incomplete, mutated, or superseded runs cannot supply
the final-test seal.

### Sealed final test

The final-test command verifies the complete full selection run and its exact
seal before reading holdout evidence. It may evaluate only sealed candidates;
it cannot tune thresholds, nominate a new scenario, or search after a rejection.

Current canonical command:

```sh
make radar-replay-final-test \
  RADAR_RESEARCH_RECOMMENDATION_SEAL=event_fade_cache/decision_radar_research_lab/runs/8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489/recommendation_seal.json \
  PYTHON=.venv/bin/python
```

If the sealed candidate set is empty, the correct final status is
`no_candidate_recommendations`. That is an auditable negative selection result,
not final-test validation of production and not permission to search the
holdout for another policy.

## Immutable runs and resumption

Each run directory is addressed by its deterministic fingerprint and contains
its protocol, input, code, configuration, manifest, persisted canonical ideas,
episode outcomes, controls, analysis, walk-forward result, policy simulation,
runtime report, and targeted review queue. The loader reads a complete run as
one no-follow, fingerprint-verified bundle.

Rerunning an identical completed configuration may report `resumed=true` and
reuse the exact immutable bytes. It must not rewrite them. A changed input,
configuration, protocol, or behavior-bearing code digest creates a different
fingerprint. Never edit a run in place, copy a loose recommendation seal, delete
superseded audit evidence, or infer authority from the newest directory.

## Publish and verify the closed report bundle

Report publication requires one explicit full selection run and its explicitly
bound final-test run. It reads immutable runs and the existing live campaign
report; it makes no provider call and does not touch dashboard authority.

Current canonical publication command:

```sh
make radar-research-reports \
  RADAR_RESEARCH_SELECTION_RUN=event_fade_cache/decision_radar_research_lab/runs/8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489 \
  RADAR_RESEARCH_FINAL_TEST_RUN=event_fade_cache/decision_radar_research_lab/runs/3009e23dd9a9f11418cf97ee07f6e532c451c21196e69bd1ae0cd6ae96c47e72 \
  PYTHON=.venv/bin/python
```

The output contract is exactly seven files, in order:

1. `research/DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.md`
2. `research/DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.json`
3. `research/DECISION_RADAR_WALK_FORWARD_REPORT.md`
4. `research/DECISION_RADAR_WALK_FORWARD_REPORT.json`
5. `research/DECISION_RADAR_POLICY_SIMULATION_REPORT.md`
6. `research/DECISION_RADAR_POLICY_SIMULATION_REPORT.json`
7. `research/DECISION_RADAR_RESEARCH_LIMITATIONS.md`

Always reproduce the bundle byte-for-byte after publication:

```sh
make radar-research-reports-check \
  RADAR_RESEARCH_SELECTION_RUN=event_fade_cache/decision_radar_research_lab/runs/8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489 \
  RADAR_RESEARCH_FINAL_TEST_RUN=event_fade_cache/decision_radar_research_lab/runs/3009e23dd9a9f11418cf97ee07f6e532c451c21196e69bd1ae0cd6ae96c47e72 \
  PYTHON=.venv/bin/python
```

The seven files form one contract, not seven independent sources of truth. The
validator binds their bundle id, protocol, source-run manifests, recommendation
seal, final confirmation, live projection, report-core digests, and rendered
Markdown/JSON agreement. Missing, extra, unsafe, oversized, changed, or spliced
bytes fail the whole semantic bundle.

## Publish and verify the separate hardening supplement

The operator-first conclusion, route-conditioned score diagnostics, and
market-wide risk grouping are published in one separately attested file. They
do not expand or rewrite the closed seven-file Protocol-v1 bundle:

```sh
make radar-research-hardening-supplement \
  RADAR_RESEARCH_SELECTION_RUN=event_fade_cache/decision_radar_research_lab/runs/8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489 \
  PYTHON=.venv/bin/python

make radar-research-hardening-supplement-check \
  RADAR_RESEARCH_SELECTION_RUN=event_fade_cache/decision_radar_research_lab/runs/8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489 \
  PYTHON=.venv/bin/python
```

The fixed output is
`research/DECISION_RADAR_EMPIRICAL_HARDENING_SUPPLEMENT.json`. It is capped at
4 MiB, canonically encoded, bound to the exact seven report hashes, the exact
selection manifest/configuration/archive hashes, and the exact diagnostics
implementation contract, and written only while all seven v1 report bytes
remain guarded. Its current supplement id is
`670bfa10b5b74ce2f213a5f6c07ace0333ae72880d62dddaee59622349eb7343`;
the current file is 3,139,732 bytes with SHA-256
`46987963a7b62abb1acdd285743705f48143c9544d2079e49e15bea630ced718`.
An identical existing file is resumed without rewriting its inode or times. A
different existing file fails closed and requires a separately reviewed,
explicitly versioned revision; the command never replaces it in place.

The new score and risk diagnostics read development and validation only. They
reject final-test/nonselection rows before reading outcomes. The concise
operator summary may copy already-sealed Protocol-v1 final-test summaries for
display only; it records that raw final-test access and holdout access are
false, and it cannot use those summaries for scenario selection. All results
remain descriptive, `policy_eligible=false`, and `auto_apply=false`.

## Interpret the Research Lab

Open the dashboard's Research Lab after the report check passes. Read the page
in this order:

1. research boundary and operator-first negative conclusion;
2. current-policy aggregate, route/regime dependence, assumed costs, score
   monotonicity, peak operator burden, evidence gaps, and missing data;
3. bundle/protocol/selection/final/seal identity;
4. sealed final verdict and production boundary;
5. partition idea, episode, and matured-outcome counts;
6. route and primary-origin coverage;
7. MFE, signed MAE, missed/false/late analysis, and matched controls;
8. walk-forward purges, selected scenarios, and zero-idea days;
9. operator burden and shadow-policy recommendations;
10. separate live no-send evidence and explicit limitations.

The dashboard acquires all seven files and the optional fixed supplement through
one descriptor-anchored read. The seven-report inventory and `7/7` bundle state
remain unchanged. It renders v1 semantics only after whole-bundle validation,
then independently validates the supplement against those exact bytes and keeps
only a bounded allowlisted operator projection. A missing, invalid, unsafe, or
oversized supplement suppresses only supplement semantics. Research can remain
visible when production authority is stale because it is historical and
non-authoritative; it never restores a current idea.

Use the status vocabulary literally:

- `no_sample`: zero eligible observations; no evidence.
- `insufficient_sample`: below the applicable frozen minimum.
- `descriptive_sample`: descriptive evidence only, not policy eligibility.
- `not_supported`: the scenario failed the frozen rule or made no material
  policy change; it is not proof of harm.
- `candidate`: eligible for pre-final sealing, never auto-applied.
- `no_candidate_recommendations`: the sealed candidate set was empty.
- walk-forward `complete`: required folds and purges completed, not causal alpha.
- `not_evaluable`: the comparison population is missing; not “no violations.”
- `violations_observed`: descriptive monotonicity counterexamples exist.

MAE is signed; a negative value is adverse excursion. Historical spread is not
observed, so cost, slippage, and adverse-selection results are assumed
sensitivity. Live no-send evidence is separately fingerprinted and never pooled
with historical replay.

## Optional human review feedback

Automatic outcome conclusions do not require human labels. To inspect the
optional append-only ledger without writing:

```sh
make radar-research-feedback-report \
  RADAR_RESEARCH_RUN_DIR=/absolute/path/to/exact-run \
  PYTHON=.venv/bin/python
```

Allowed labels are `useful`, `not_useful`, `too_late`, `too_noisy`,
`manipulation_concern`, `correct_risk_warning`, `missed_confirmation`,
`duplicate`, and `data_problem`. Append one only after matching the exact queue
item and supplying a real observation time:

```sh
CONFIRM=1 make radar-research-feedback-mark \
  RADAR_RESEARCH_RUN_DIR=/absolute/path/to/exact-run \
  RADAR_RESEARCH_REVIEW_ITEM_ID=exact-review-item-id \
  RADAR_RESEARCH_REVIEW_LABEL=useful \
  RADAR_RESEARCH_REVIEW_OBSERVED_AT=2026-07-16T08:31:35Z \
  PYTHON=.venv/bin/python
```

Feedback is human-supplied preference metadata. It cannot change evidence
bytes, scoring, selection, production policy, or dashboard authority.

## Bounded source-with-artifacts and optional history exports

The checked-in project artifact policy is the top-level selection authority for
the normal review ZIP. It keeps only exact operator controls, the current
pointer-selected generation, the latest genuine live/no-send attempt
generation, bounded shared campaign/calendar/source-contract state, and the
canonical selection delegated to the empirical policy. Fixture, rehearsal,
failed, intermediate, superseded, and historical artifacts are excluded from
the normal archive without being deleted, moved, compacted, or rewritten.

Build the normal overwrite-in-place review archive with:

```sh
make export-src-with-artifacts PYTHON=.venv/bin/python
```

Export the exact disjoint complement of the standard project selection only
when complete historical review is needed:

```sh
make export-project-artifact-history PYTHON=.venv/bin/python
```

That command may write only the fixed ignored file
`crypto_rsi_scanner_artifact_history.zip`. It carries immutable per-file
fingerprints, a manifest, and checksums. Missing optional current sources stay
explicit in the standard manifest as partial coverage; they are never treated
as healthy-empty.

Within that top-level policy, the checked-in empirical artifact policy defines
the exact canonical fixture, medium, selection, and final-test runs; frozen
protocol and Protocol-v2 readiness artifacts; seven v1 reports; separate
hardening supplement; and optional bounded feedback ledger. The narrower
empirical-only history complement remains available for lab-specific review:

```sh
make export-empirical-artifact-history PYTHON=.venv/bin/python
```

The empirical history command may write only the fixed ignored file
`crypto_rsi_scanner_empirical_artifact_history.zip`. None of the exporters
deletes, moves, compacts, or rewrites input evidence. Missing policy/lab data, manifest
drift, unmanifested canonical files, invalid feedback, excluded noise,
symlinks, path replacement, bounds violations, secrets, or archive collisions
fail closed and preserve any prior successful archive.

The project-wide hardening inventory is explicit and additive: 2,439 eligible
artifacts split into 161 canonical files and 2,278 history files. The nested
lab inventory remains 439 regular files / 972,516,087 logical bytes; its
standard selection retains 76 lab files / 194,084,656 logical bytes and its
lab-specific history complement has 363 files / 778,431,431 logical bytes. Each
standard/history pair is disjoint and reconciles to its complete inventory.
Archive compression is reported by each command; it is not used as a retention
rule.

### Platform-truthful release evidence

Treat the locked local runtime and an extracted Linux source-with-artifacts
checkout as separate release observations. Record the operating system,
architecture, Python version, archive SHA-256, and exact commands for each.
Passing on one platform must never be reported as passing on the other.

On the current Mac, use the locked `.venv` and run the complete local ladder.
For Linux, transfer the already-built review archive through an approved secure
channel, extract it without changing its contents, then run:

```sh
make test-artifact-heavy-extracted-checkout PYTHON=python3
make verify-fast PYTHON=python3
make verify PYTHON=python3
```

If no Linux runtime has the exact archive, record Linux archive verification as
`pending_unavailable`, not green. GitHub source-only CI is useful additional
evidence, but it is not a substitute when the ignored empirical artifact store
is absent from the runner. Unsupported descriptor/no-follow behavior must fail
closed; do not skip its security regressions.

## Current canonical evidence

- selection run: `8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489`;
- final-test run: `3009e23dd9a9f11418cf97ee07f6e532c451c21196e69bd1ae0cd6ae96c47e72`;
- report bundle: `267a1c6d30488fcd7088bf20ce6f653df6bf79f82c5e7d401e27fd4b24debbcf`;
- recommendation seal: `3f0ea69c2cb3c455bf9d8e13f44f6db6cee6308192c61a090b9f39e0a5442639`;
- hardening supplement id: `670bfa10b5b74ce2f213a5f6c07ace0333ae72880d62dddaee59622349eb7343`;
- final status: `no_candidate_recommendations`;
- production policy: unchanged.

All nine material shadow alternatives are `not_supported`. Historical samples
exist only for market-led `dashboard_watch`, `risk_watch`, and `diagnostic`.
Five routes and six primary origins have zero empirical episodes. Historical
spread and intraday execution remain unavailable, and the live no-send lane is
still an insufficient separate observational sample. Preserve earlier runs and
bundles as immutable superseded audit evidence; never use them as the current
selection input.

Within-route diagnostics do not justify retuning: `dashboard_watch` has no
evaluable adjacent score-bucket pair in either selection partition, while
`risk_watch` actionability has one descriptive violation among two evaluable
adjacent pairs in both development and validation. Outcome-blind daily grouping
finds 2,412 selection-period risk items across 411 partition-specific UTC days;
130 partition-days contain at least three distinct affected assets. Development
and validation are never pooled even if their date labels overlap.
Correlated-family suppression remains
explicitly not evaluable because the replay lacks the required correlation and
family lineage.

## Failure handling

- Protocol check failure: stop; do not run replay or edit the frozen contract to
  match observed output.
- Input or warm-up gap: retain the explicit missing/unavailable basis; do not
  backfill with future data or current metadata.
- Incomplete or mutated run: do not use its seal, reports, or review queue.
- Final-test binding failure: stop; do not copy a seal or weaken digest checks.
- Report check drift: treat the full seven-file bundle as invalid and regenerate
  only from the exact immutable selection/final pair.
- `not_evaluable`: report the missing comparison population; do not convert it
  to a pass.
- No candidate recommendations: preserve the negative result and production
  policy; do not lower thresholds to create a candidate.
- Missing spread or intraday data: keep execution evidence unavailable and label
  every cost result assumed.

## Next safe command

The universal no-provider starting point is:

```sh
make radar-research-protocol-check PYTHON=.venv/bin/python
```

For the current canonical evidence, the exact non-writing reproducibility check
is the `radar-research-reports-check` command above with the exact locked run
fingerprints `8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489`
and `3009e23dd9a9f11418cf97ee07f6e532c451c21196e69bd1ae0cd6ae96c47e72`.
