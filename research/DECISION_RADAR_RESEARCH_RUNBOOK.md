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

## Interpret the Research Lab

Open the dashboard's Research Lab after the report check passes. Read the page
in this order:

1. bundle/protocol/selection/final/seal identity;
2. final verdict and production boundary;
3. partition idea, episode, and matured-outcome counts;
4. route and primary-origin coverage;
5. score monotonicity;
6. MFE, signed MAE, missed/false/late analysis, and matched controls;
7. assumed costs and route survivability;
8. walk-forward purges, selected scenarios, and zero-idea days;
9. operator burden and shadow-policy recommendations;
10. separate live no-send evidence and explicit limitations.

The dashboard acquires all seven files through one descriptor-anchored read and
renders semantic tables only after whole-bundle validation. If validation fails,
only the bounded inventory and failure state may remain. Research can remain
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

## Current canonical evidence

- selection run: `8212b2ddb626805f4312d8986cc1d9f6b3229a169aa49ca75b9b5bbfc1660489`;
- final-test run: `3009e23dd9a9f11418cf97ee07f6e532c451c21196e69bd1ae0cd6ae96c47e72`;
- report bundle: `267a1c6d30488fcd7088bf20ce6f653df6bf79f82c5e7d401e27fd4b24debbcf`;
- recommendation seal: `3f0ea69c2cb3c455bf9d8e13f44f6db6cee6308192c61a090b9f39e0a5442639`;
- final status: `no_candidate_recommendations`;
- production policy: unchanged.

All nine material shadow alternatives are `not_supported`. Historical samples
exist only for market-led `dashboard_watch`, `risk_watch`, and `diagnostic`.
Five routes and six primary origins have zero empirical episodes. Historical
spread and intraday execution remain unavailable, and the live no-send lane is
still an insufficient separate observational sample. Preserve earlier runs and
bundles as immutable superseded audit evidence; never use them as the current
selection input.

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
