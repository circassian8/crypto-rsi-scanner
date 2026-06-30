# DEVLOG — change history

This project now has **local git** for diffs/rollback, while this file remains
the human-readable narrative history. **Newest entries at the top**, just under
this header. Append (prepend) one entry per non-trivial change. Keep it skimmable;
deep reasoning can link to code. See `AGENTS.md` for the working agreement.

### Entry template (copy this)

```
## YYYY-MM-DD — <short title> · <Claude|Codex|human>
**Why:** one or two sentences of motivation.
**Changes:** bullet list, with file references.
**Verify:** what you ran and the result (tests, dry-run, backtest…).
**Notes/risks:** anything the next agent should know. Optional.
```

---

## 2026-06-30 — Reconcile deep rehearsal core-card coverage · Codex
**Why:** The full Prompt 10 artifact audit found that the `notify_llm_deep`
no-send rehearsal could write visible canonical CoreOpportunity rows that were
hidden by aggregation and therefore never received research-card paths or
feedback targets. Strict artifact doctor correctly blocked send-readiness.
**Changes:**
- Research-card selection now keeps the aggregation-first operator ordering, but
  appends any store-backed core rows that aggregation omitted so the canonical
  core store, card index, feedback targets, and artifact doctor stay
  reconciled.
- Added a regression proving an aggregated generic-support core row still gets a
  card and can be linked back into `event_core_opportunities.jsonl`.
**Verify:** `python3 tests/test_indicators.py` (577/577 passed);
`make event-alpha-notify-llm-deep-real-no-send-rehearsal-fast PYTHON=python3`
now writes 245 core rows/cards and strict doctor has no blockers;
`make event-alpha-artifact-doctor PROFILE=notify_llm_deep_rehearsal STRICT=1 PYTHON=python3`;
`make event-alpha-send-readiness PROFILE=notify_llm_deep_rehearsal PYTHON=python3`
reports `READY_FOR_NO_SEND_REHEARSAL_REVIEW: yes`.
**Notes/risks:** Artifact/card consistency only. It does not change scoring,
routes, notification sends, paper/live rows, normal RSI rows, or
`TRIGGERED_FADE`.

## 2026-06-30 — Promote CryptoPanic and exchange evidence contracts · Codex
**Why:** CryptoPanic token-tagged news and official exchange announcements are
the highest-value source families for Event Alpha validation, but they need
strict identity semantics so hot/bullish news or unrelated listings cannot
confirm weak candidates.
**Changes:**
- CryptoPanic source assessment now only treats tagged rows as token-identity
  and impact-path proof when the currency tag matches the validated symbol or
  coin id; tag mismatches and narrative-heat-only rows remain capped/rejected.
- Source packs now treat tagged CryptoPanic as preferred evidence for security,
  fan/sports, political meme, and strategic/business paths where it was already
  allowed as impact-validating evidence.
- Official Binance/Bybit announcement evidence now validates acquisition rows
  through parsed exchange symbol/pair/contract metadata, while unrelated
  official listings are rejected as token-identity mismatches.
- Added regressions for CryptoPanic currency query filters, matched/mismatched
  tags, official listing/perp metadata, source-pack validation, and the
  watchlist/high-priority need for later market/derivatives confirmation.
**Verify:** `python3 tests/test_indicators.py` (576/576 passed);
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`;
`make event-alpha-source-coverage-report PROFILE=evidence_acquisition_smoke PYTHON=python3`;
`make verify PYTHON=python3`.
**Notes/risks:** Research-only evidence contract change. This does not weaken
strict alert gates, send Telegram, paper/live trade, write normal RSI rows, or
create `TRIGGERED_FADE`.

## 2026-06-30 — Harden Event Alpha feedback calibration fields · Codex
**Why:** Feedback labels should be useful calibration rows even when the matched
core/card/watchlist context carries source-pack and quality fields outside the
latest score components.
**Changes:**
- Feedback recording now falls back to the matched canonical row/context for
  top-level calibration fields including source class/domain, evidence
  specificity, impact path, candidate role, opportunity level, market
  confirmation, and source pack.
- Strengthened the feedback/calibration regression so `source_pack` is proven
  from the canonical context row rather than only from nested score components.
- Documented that top-level feedback dimensions are the calibration contract;
  nested metadata remains audit context only.
**Verify:** `python3 tests/test_indicators.py` (574/574 passed);
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`;
`make event-alpha-feedback-readiness PROFILE=catalyst_frame_e2e PYTHON=python3`;
`make event-feedback-useful PROFILE=catalyst_frame_e2e FEEDBACK_TARGET=agg:3381ebd96566 PYTHON=python3`;
`make event-alpha-calibration-report PROFILE=catalyst_frame_e2e PYTHON=python3`;
`make event-alpha-export-signal-quality-cases PROFILE=catalyst_frame_e2e PYTHON=python3`;
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`;
`make event-alpha-quality-validation-cycle PYTHON=python3`;
`make verify PYTHON=python3`.
**Notes/risks:** Research-only calibration artifact change. This does not alter
routes, alertability, notification sends, paper/live rows, normal RSI rows, or
`TRIGGERED_FADE`.

## 2026-06-30 — Polish Event Alpha burn-in review queue · Codex
**Why:** Research-review burn-in needs a small operator-facing queue instead of
row dumps, while source-noise/control diagnostics stay out of the default
phone-friendly inbox.
**Changes:**
- Added a ranked Event Alpha review queue model for strict would-send items,
  high-priority/digest lanes, research-review near-misses, upgrade candidates,
  local-only learning rows, and diagnostics.
- The burn-in inbox now shows a compact ranked queue first, with card basenames
  instead of absolute paths and feedback commands per item.
- Diagnostic/source-noise/ticker-collision controls are hidden from the default
  ranked queue and remain available through full diagnostic surfaces; local-only
  row counts stay collapsed in burn-in review.
- Added regression coverage proving VELVET ranks first, DOGE appears as a
  research-review near-miss, BTC control noise is hidden by default, and local
  card paths are not exposed in the compact inbox.
**Verify:** `python3 tests/test_indicators.py` (574/574 passed);
`make event-alpha-research-review-digest-smoke PYTHON=python3`;
`make event-alpha-notify-llm-deep-research-review-no-send-smoke PYTHON=python3`;
`make event-alpha-telegram-no-send-final-check-fast PYTHON=python3`;
`make verify PYTHON=python3`.
**Notes/risks:** Presentation-only. This does not change Event Alpha scoring,
quality gates, alertability, Telegram send guards, paper/live rows, normal RSI
rows, or `TRIGGERED_FADE` ownership.

## 2026-06-30 — Add Event Alpha LLM analyst tools · Codex
**Why:** Catalyst-frame analysis is not the only useful LLM layer. Operators
also need constrained source triage, evidence planning, contradiction checks,
manual verification prompts, and concise summaries without letting LLMs decide
routes, trades, or `TRIGGERED_FADE`.
**Changes:**
- Added a quote-checked LLM source-triage schema on top of deterministic source
  enrichment, including page type, real-article status, official/recap/SEO
  flags, mechanism evidence quote, confidence, and deterministic override caps.
- Extended the evidence planner with v2 metadata: query intents, official
  confirmation queries, denial/correction queries, expected proof criteria,
  manual checklist, contradiction/denial status, analyst summaries, and
  explicit LLM analyst-tool budget counters.
- Research cards now show a deterministic Analyst Summary block with why the
  candidate surfaced, why it is or is not alertable, what would upgrade it,
  what would invalidate it, and what to check next.
- Added regression tests for source triage validation, SEO/official/good
  source handling, unsupported LLM output rejection, contradiction/denial
  detection, analyst-summary copy, and budget caps/missing-key behavior.
**Verify:** `python3 tests/test_indicators.py` (574/574 passed);
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`;
`python3 -m compileall -q crypto_rsi_scanner tests`;
`make verify PYTHON=python3`.
**Notes/risks:** Research-only. These tools can improve operator context and
planning, but deterministic source/identity/quality validators remain
authoritative and LLM output cannot send notifications, trade, paper trade,
write normal RSI rows, or create `TRIGGERED_FADE`.

## 2026-06-30 — Harden Event Alpha asset-role identity · Codex
**Why:** Candidate assets can be over-promoted when taxonomy suggestions,
common-word tickers, broad macro assets, or venue tokens are treated as directly
affected assets without source evidence explaining the actual role.
**Changes:**
- Added deterministic asset knowledge and role capabilities for core assets
  such as BTC/ETH/SOL, RUNE/THORChain, AAVE, VELVET, HYPE, CHZ, TRUMP, LINK,
  KCS, stablecoins, and wrapped assets.
- Resolver and impact-path validation now persist identity confidence,
  identity evidence, matched field/alias, role source, collision risk, asset
  kind, role capabilities, and role-validation failures/warnings.
- Taxonomy/LLM suggestions stay diagnostic unless source text directly ties the
  asset identity to the mechanism; broad macro assets are capped to contextual
  roles when the article is not really about the coin.
- Event classification now distinguishes proxy instruments from proxy venues
  using asset capabilities plus text context, preserving historical TEST*
  event-fade fixture behavior and keeping `TRIGGERED_FADE` controlled by
  `event_fade.py`.
- Cards, opportunity audits, daily briefs, watchlist rows, and canonical core
  rows surface compact identity metadata for operator review.
**Verify:** `python3 tests/test_indicators.py` (572/572 passed);
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`;
`make event-alpha-source-coverage-report PROFILE=evidence_acquisition_smoke
PYTHON=python3`; `python3 -m compileall -q crypto_rsi_scanner tests`.
**Notes/risks:** Research-only. Asset knowledge can reject or cap weak roles,
but it cannot send Telegram, trade, paper trade, write normal RSI rows, or
create `TRIGGERED_FADE`.

## 2026-06-30 — Rebuild source enrichment quality gates · Codex
**Why:** Google News placeholders, ticker-sidebar pages, blocked pages, and
affiliate/SEO article text can poison Event Alpha LLM extraction, catalyst
frames, evidence scoring, and notification quality if treated like reliable
source bodies.
**Changes:**
- Source enrichment cache rows now use schema v3 and persist extractor/cleaner
  versions, fetched/final/canonical URLs, redirect chains, article metadata,
  cleaned body text, body length, boilerplate ratio, ticker-sidebar detection,
  article quality status, and deterministic source triage metadata.
- LLM raw-event extraction and catalyst-frame packets now only consume enriched
  article bodies when the quality gate says the body is usable (`good` or
  `fixture_text_used`); placeholders, blocked pages, thin pages, boilerplate,
  SEO/referral pages, recap pages, and context-only prediction-market rows stay
  as raw summaries or diagnostics.
- Added a fixture-backed optional source-quality judge interface whose output is
  constrained by deterministic triage, so unsafe LLM source-quality output
  cannot override hard quality caps.
- Evidence acquisition samples now carry source-enrichment metadata, and cards,
  opportunity audits, daily briefs, and source-coverage reports show article
  quality when evidence rows include it.
- Expanded tests for Google News placeholders, anti-bot/403 pages, ticker-heavy
  boilerplate pages, fixture text, good articles, triage decisions, source
  quality judge fixtures, LLM body gating, and article-quality source coverage.
**Verify:** `python3 tests/test_indicators.py` (568/568 passed);
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`;
`make event-alpha-source-coverage-report PROFILE=evidence_acquisition_smoke
PYTHON=python3`; `make verify PYTHON=python3`; `python3 -m compileall -q
crypto_rsi_scanner tests`.
**Notes/risks:** Research-only. Article/source quality can cap or diagnose LLM
source text, but it cannot validate candidates, send Telegram, trade, paper
trade, write normal RSI rows, or create `TRIGGERED_FADE`.

## 2026-06-30 — Add advanced Event Alpha market confirmation · Codex
**Why:** Event Alpha source and impact-path validation was stronger, but
operator-facing market confirmation was still too spot-price-centric. Derivative
crowding, DEX liquidity, and protocol metrics should inform playbook-specific
confirmation without proving the catalyst by themselves.
**Changes:**
- Market confirmation now scores fresh derivatives evidence from OI, funding,
  liquidations, long/short crowding, and futures volume, with separate
  derivatives freshness, level, score, and reason fields.
- Added fixture-ready DEX liquidity and protocol-metric confirmation paths for
  liquidity sanity, DEX volume/new-pool context, TVL outflows/growth, fees, and
  protocol volume.
- Watchlist enrichment can now carry DEX liquidity and protocol metrics through
  fixture/provider abstractions, while core opportunity rows, cards, audits,
  daily briefs, quality review, and verdict explanations expose the new
  confirmation layers.
- Source packs and source registry now request Coinalyze/GeckoTerminal/
  DefiLlama-style evidence where relevant while keeping identity, catalyst-link,
  impact-path, source-quality, live-confirmation, and event-fade gates strict.
- Expanded tests for perp/listing derivatives, stale/missing derivatives,
  DEX liquidity caps/support, protocol TVL/fee confirmation, playbook-specific
  interpretation, source-pack gaps, and watchlist enrichment fixtures.
**Verify:** `python3 tests/test_indicators.py` (566/566 passed);
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`;
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`;
`make verify PYTHON=python3`; `python3 -m compileall -q crypto_rsi_scanner
tests`.
**Notes/risks:** Research-only. Advanced market data can support, cap, or
explain opportunity quality, but it cannot prove identity/catalyst/impact path,
send Telegram, write normal RSI rows, trade, paper trade, or create
`TRIGGERED_FADE`.

## 2026-06-30 — Promote structured calendar and unlock source packs · Codex
**Why:** CoinMarketCal-style dated catalysts and Tokenomist-style unlock rows
were parsed, but Event Alpha did not preserve enough structured proof or enforce
enough pack-specific obligations to make them first-class evidence in source
coverage, acquisition, cards, and audits.
**Changes:**
- CoinMarketCal normalization now preserves structured calendar metadata
  including event-time provenance, source class/mission, event category,
  confirmation/source confidence, original source URL, and token identity.
- Tokenomist normalization now preserves structured unlock metadata including
  event-time provenance, unlock type/category, token identity, normalized unlock
  percentage, materiality, and structured supply source class.
- Source registry and source packs now expose structured calendar/unlock source
  contracts, add a `project_event_pack`, require material/non-stale unlock
  evidence for digest/watchlist promotion, and keep low-authority calendar rows
  local/review-only.
- Evidence acquisition, research cards, opportunity audits, provider wiring,
  and LLM evidence planning now understand `coinmarketcal` and `tokenomist`
  provider evidence as bounded research acquisition sources with compact
  structured metadata in accepted samples.
- Expanded fixture tests for provider parsing, source-pack sufficiency,
  material/stale unlock gates, project-event calendar gates, and structured
  Tokenomist acquisition/card/audit display.
**Verify:** `python3 tests/test_indicators.py` (566/566 passed);
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`;
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`;
`make event-alpha-source-coverage-report PROFILE=evidence_acquisition_smoke
PYTHON=python3`; `make verify PYTHON=python3`;
`python3 -m compileall -q crypto_rsi_scanner tests`.
**Notes/risks:** Research-only. Structured calendar/unlock evidence can support
source-pack confirmation only through deterministic identity, catalyst-link,
impact-path, source-quality, live-confirmation, router, and `event_fade.py`
gates. It does not send Telegram, write normal RSI rows, trade, paper trade, or
create `TRIGGERED_FADE`.

## 2026-06-30 — Make CryptoPanic and exchange evidence first-class · Codex
**Why:** CryptoPanic token-tagged news and official exchange announcements are
the highest-value confirmation sources for several Event Alpha source packs, but
their accepted evidence samples did not preserve enough provider-specific proof
for cards, audits, and daily briefs.
**Changes:**
- CryptoPanic catalyst searches now query by validated symbol plus coin slug by
  default, accepted/rejected evidence preserves currency tags, tag-match status,
  and narrative-heat metadata, and tag mismatches or hot/bullish-only posts get
  explicit rejection reasons.
- Binance/Bybit announcement normalization now records official exchange source
  metadata, event kind, product type, symbols, pairs/contracts, announcement
  timestamps, and source URLs; it also recognizes delisting and
  launchpool/earn/product announcements while rejecting unrelated operational
  updates.
- Research cards, opportunity audits, and daily briefs now surface accepted
  evidence source classes plus compact CryptoPanic tag and official-exchange
  pair/contract details without changing alert gates.
- Expanded tests for CryptoPanic currency filtering/tag validation, heat-only
  rejection, official exchange listing/perp metadata, delisting/product
  normalization, and source-class reporting.
**Verify:** `python3 tests/test_indicators.py` (565/565 passed);
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`;
`make event-alpha-source-coverage-report PROFILE=evidence_acquisition_smoke
PYTHON=python3`; `make verify PYTHON=python3`.
**Notes/risks:** Research-only. This adds stronger evidence acquisition and
display semantics only; it does not weaken strict alert gates, send Telegram,
write normal RSI rows, paper trade, live trade, or create `TRIGGERED_FADE`.

## 2026-06-30 — Harden Event Alpha source-system coverage semantics · Codex
**Why:** Source coverage reports needed to distinguish missing providers,
role-specific degradation, and non-confirming evidence more explicitly so
operators can tell when an absence is a coverage gap instead of negative proof.
**Changes:**
- Added pack-level `provider_coverage_status` / `source_pack_coverage_status`,
  role-specific provider health, explicit coverage-gap reasons, and
  missing/degraded confirmation-provider lists to source coverage rows and
  reports.
- Added artifact-doctor checks for source-coverage metadata gaps,
  missing provider recommendations, and contradictory meaningful-absence claims
  when coverage is degraded, unavailable, or not configured.
- Expanded source coverage tests to cover degraded role health, unavailable and
  not-configured packs, explicit gap reasons, and strict-doctor warnings.
- Updated roadmap, decision notes, and the Event Alpha runbook to record the
  new source-system interpretation.
**Verify:** `python3 tests/test_indicators.py` (563/563 passed);
`make event-alpha-source-coverage-report PROFILE=notify_llm_deep_rehearsal
PYTHON=python3`; `make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-research-review-digest-smoke PYTHON=python3`;
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`;
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`;
`make verify PYTHON=python3`.
**Notes/risks:** Research-only. This adds diagnostics and artifact-doctor
guardrails only; it does not change source eligibility, alert routing, normal
RSI alerts, paper/live writes, or `TRIGGERED_FADE`.

## 2026-06-30 — Operationalize notify-deep research-review digest · Codex
**Why:** The fixture research-review digest worked, but real-profile
`notify_llm_deep` rehearsals did not expose research-review lane accounting, so
near-miss candidates could disappear behind heartbeat-only previews. Source
coverage also needed clearer next-provider guidance without weakening strict
alert gates.
**Changes:**
- Threaded `research_review_digest` enabled/candidate/would-send/sent/block
  counters through notification send results, pipeline results, run ledgers, and
  run-ledger reports.
- Added a strict artifact-doctor check for latest runs that have
  research-review candidates but no `research_review_digest` delivery row.
- Added `make event-alpha-notify-llm-deep-research-review-no-send-smoke` to
  prove the real `notify_llm_deep` profile writes blocked no-send
  research-review delivery rows for fixture near-misses.
- Updated the compact Telegram no-send final check so its fixture rehearsal
  enables and reports the separate `research_review_digest` lane alongside
  strict lanes.
- Expanded source coverage reports with actionable per-pack provider, setup,
  budget, rejected-only, and provider-health recommendations.
- Updated runbook, roadmap, and decision notes for the operational
  research-review lane.
**Verify:** `python3 tests/test_indicators.py` (563/563 passed);
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-notify-llm-deep-research-review-no-send-smoke PYTHON=python3`;
`make event-alpha-research-review-digest-smoke PYTHON=python3`;
`make event-alpha-notification-format-smoke PYTHON=python3`;
`make event-alpha-telegram-no-send-final-check-fast PYTHON=python3`;
`make event-alpha-source-coverage-report PROFILE=notify_llm_deep_rehearsal
PYTHON=python3`; `make event-alpha-live-burn-in-no-send PYTHON=python3`;
`make verify PYTHON=python3`.
**Notes/risks:** Research-only. This does not change strict alert eligibility,
normal RSI alerts, paper/live writes, or `TRIGGERED_FADE`. The live burn-in
still reports expected external-provider/LLM instability as warnings
(GDELT 429, RSS 403/timeouts, OpenAI timeouts/resets), not blockers.

## 2026-06-29 — Add Event Alpha source coverage dashboard · Codex
**Why:** Live/rehearsal runs can stay quiet because source-pack evidence is
missing, degraded, skipped by budget, or rejected. Operators needed one
research-only view that answers which provider/source pack would most improve
the next run without weakening alert gates.
**Changes:**
- Added `event_alpha_source_coverage.py`, a read-only source-pack dashboard
  that combines provider readiness, provider health, evidence-acquisition rows,
  and canonical core rows into configured/missing/healthy/degraded provider
  coverage, non-confirming acquisition outcomes, meaningful-absence flags, and
  candidate coverage blockers.
- Added `main.py --event-alpha-source-coverage-report` and
  `make event-alpha-source-coverage-report PROFILE=...`.
- Added daily-brief copy that names the data source most likely to improve the
  next run, plus source-pack vocabulary for CoinGecko/DefiLlama market and
  protocol metrics. DefiLlama is treated as market-confirmation evidence, not
  impact-path validation.
- Added offline tests for the coverage report, Make target, and DefiLlama source
  registry semantics.
**Verify:** `python3 tests/test_indicators.py` (563/563 passed);
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-research-review-digest-smoke PYTHON=python3`;
`make event-alpha-source-coverage-report PROFILE=notify_llm_deep_rehearsal
PYTHON=python3`; `make event-alpha-evidence-acquisition-smoke PYTHON=python3`;
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`;
`make verify PYTHON=python3`.
**Notes/risks:** Research-only. The report does not send, trade, paper trade,
write normal RSI rows, promote candidates, or create `TRIGGERED_FADE`.

## 2026-06-29 — Add Event Alpha research-review digest lane · Codex
**Why:** During notification burn-in, strict alert lanes can correctly send only
a heartbeat even when there are useful near-miss candidates worth operator
review. The user wanted those review leads delivered without weakening
high-priority/watchlist/validated-digest gates.
**Changes:**
- Added a separate `research_review_digest` notification lane with its own
  config, cooldown, delivery ledger records, preview rendering, inbox section,
  daily-brief section, and strict artifact-doctor checks.
- The lane selects only non-alertable exploratory/local near-misses with
  validated identity and sufficient score, excluding strict alertable rows,
  sector-only rows by default, source-noise, ticker collisions,
  generic-cooccurrence rows, diagnostics, and support/control rows.
- Added Telegram copy that clearly says the item is research review only,
  not alertable, missing confirmation, and not a trade signal, while hiding raw
  ids, absolute paths, JSON dumps, and enum spam.
- Added `make event-alpha-research-review-digest-smoke`, fixture near-miss
  coverage, burn-in profile defaults, `.env.example` knobs, tests, and runbook
  notes.
**Verify:** `python3 tests/test_indicators.py` (562/562 passed);
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-research-review-digest-smoke PYTHON=python3`;
`make event-alpha-notification-format-smoke PYTHON=python3`;
`make event-alpha-notify-llm-deep-no-send-smoke PYTHON=python3`;
`make event-alpha-telegram-no-send-final-check-fast PYTHON=python3`;
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`;
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`;
`python3 main.py --event-alpha-daily-brief --event-alpha-profile fixture
--event-alpha-artifact-namespace research_review_digest_smoke
--event-alpha-include-test-artifacts`; `make verify PYTHON=python3`.
**Notes/risks:** Research-only. This lane does not make candidates alertable,
does not alter strict alert gates, and cannot create `TRIGGERED_FADE`. Tests and
smokes do not send Telegram.

## 2026-06-29 — Fix Event Alpha notification SLO CLI wrapper · Codex
**Why:** A real `notify_llm_deep` Telegram send succeeded, but the follow-up
SLO report crashed because the CLI passed the diagnostics flag into a wrapper
that did not accept it.
**Changes:**
- Updated `event_alpha_notification_slo_report` to accept the optional
  `include_diagnostics` flag used by the CLI while preserving existing SLO
  report behavior.
- Added a regression assertion that the operational SLO wrapper exposes the
  diagnostics-compatible parameter, and refreshed the artifact-doctor preview
  fixture to use the current portable preview-path contract.
**Verify:** `make event-alpha-notification-slo-report PROFILE=notify_llm_deep
PYTHON=python3`; targeted SLO/artifact-doctor regression calls; `python3
tests/test_indicators.py` (559/559 passed); `python3 -m compileall -q
crypto_rsi_scanner tests`; `make verify PYTHON=python3`.
**Notes/risks:** The real send delivered the heartbeat notification before this
fix. The `notify_llm_deep` namespace remains artifact-doctor blocked by stale
pre-canonical rows and missing core card/feedback coverage, so use the
rehearsal namespace for send-readiness gates until that artifact hygiene is
cleaned.

## 2026-06-29 — Add one-cycle Event Alpha Telegram send gates · Codex
**Why:** The deterministic no-send rehearsal is now clean, but the real-send
operator path needed a separate preflight, explicit one-cycle send guard, and
post-send audit so Telegram can be re-enabled safely for exactly one cycle.
**Changes:**
- Added `make event-alpha-telegram-one-cycle-send-preflight`, which reuses the
  compact final artifact check, writes a profile-scoped preflight marker, and
  never sends Telegram.
- Added `make event-alpha-telegram-send-one-cycle`, which refuses unless
  `RSI_EVENT_ALERTS_ENABLED=1`, Telegram token/chat config is present,
  `CONFIRM=1` or a preflight marker exists, and the rehearsal namespace passes
  the compact final check immediately before sending.
- Added `make event-alpha-telegram-post-send-audit` and the
  `make event-alpha-notification-pause` alias so the operator can audit the
  delivered lanes/items immediately and pause sends with an obvious command.
- Updated compact final-check copy, Make help, tests, roadmap, decisions, and
  the Event Alpha runbook to point real sends through the guarded one-cycle
  target instead of a scheduled target.
**Verify:** `python3 tests/test_indicators.py` (559/559 passed);
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-notification-format-smoke PYTHON=python3`;
`make event-alpha-notify-llm-deep-no-send-smoke PYTHON=python3`;
`make event-alpha-telegram-no-send-final-check-fast PYTHON=python3`;
`make event-alpha-telegram-one-cycle-send-preflight PROFILE=notify_llm_deep_fixture_rehearsal PYTHON=python3`;
`make event-alpha-telegram-send-readiness-final PROFILE=notify_llm_deep_fixture_rehearsal PYTHON=python3`;
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`;
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`;
`make verify PYTHON=python3`.
**Notes/risks:** Research-only notification operations. Tests do not send
Telegram. No trading, paper trading, normal RSI rows, or provider/LLM-created
`TRIGGERED_FADE`.

## 2026-06-29 — Add fast Event Alpha Telegram final check · Codex
**Why:** The full `notify_llm_deep` no-send final check can still spend minutes
in provider-failure environments. Operators need a fast deterministic last
check for formatting, canonical identity, preview path, and send-readiness
without touching live providers.
**Changes:**
- Added `event_alpha_telegram_final_check.py` and
  `main.py --event-alpha-telegram-final-check`, a compact read-only final
  Telegram gate built from existing run, delivery, core, doctor, readiness, and
  go/no-go artifacts.
- Reworked `make event-alpha-telegram-no-send-final-check-fast` so it no longer
  uses recursive Make. It rebuilds deterministic
  `notify_llm_deep_fixture_rehearsal` artifacts, captures noisy report output,
  then prints only the compact final check: status, preview path, strict doctor
  status, would-send lanes, core ids, send count, provider summary, and next
  commands.
- Added `make event-alpha-telegram-send-readiness-final` and
  `make event-alpha-telegram-final-send-checklist` as read-only compact gates
  for existing namespaces; both fail through the compact check when the
  namespace is `NOT_READY`.
- Go/no-go and artifact doctor now warn explicitly when a namespace contains
  stale pre-canonical notification delivery rows and should not be trusted for
  send-readiness.
- Updated Make help, runbook, roadmap, and decisions to distinguish the fast
  deterministic check, the slower live-provider no-send rehearsal, and actual
  guarded sends.
**Verify:** `python3 tests/test_indicators.py` (559/559 passed);
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-notification-format-smoke PYTHON=python3`;
`make event-alpha-notify-llm-deep-no-send-smoke PYTHON=python3`;
`make event-alpha-telegram-no-send-final-check-fast PYTHON=python3`;
`make event-alpha-telegram-send-readiness-final PROFILE=notify_llm_deep_fixture_rehearsal PYTHON=python3`;
`make event-alpha-live-burn-in-no-send PYTHON=python3`;
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`;
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`;
`make verify PYTHON=python3`.
**Notes/risks:** Research-only notification workflow polish. No Telegram sends
in tests, no live trading, no paper trading, no normal RSI rows, and no
LLM/provider path can create `TRIGGERED_FADE`.

## 2026-06-29 — Finalize Event Alpha notification go/no-go · Codex
**Why:** The deep notification rehearsal had artifact-level readiness checks,
but operators still needed one compact final go/no-go report and a readable
preview summary before enabling real Telegram sends.
**Changes:**
- `--event-alpha-notify-go-no-go` now inspects the same profile/namespace
  artifacts as send-readiness, including latest run completion, preview path
  resolution, explicit delivery status, canonical core identity, alertable item
  count, would-send lanes, and a final `READY_FOR_NO_SEND_REVIEW` /
  `READY_FOR_SEND` / `NOT_READY` recommendation.
- Notification previews now include a concise top-level summary with mode,
  would-send status, lane counts, included candidates, send-guard wording, and
  operator next step; preview card paths are rendered as portable labels rather
  than machine-local absolute paths.
- Added `make event-alpha-send-go-no-go` and
  `make event-alpha-telegram-no-send-final-check`; the deterministic deep
  fixture rehearsal now also runs go/no-go, burn-in inbox, and daily brief
  checks.
**Verify:** `python3 tests/test_indicators.py` passed (559/559). Full prompt
verification and export run after this doc update before commit/push.
**Notes/risks:** Research-only notification readiness/UX polish. No Telegram
sends in tests, no trades, no paper trades, no normal RSI rows, and no
LLM/provider path can create `TRIGGERED_FADE`.

## 2026-06-29 — Make Event Alpha delivery status explicit · Codex
**Why:** The deep notification rehearsal could infer useful delivery status in
reports, but the delivery ledger itself still allowed fresh rows with
machine-readable status fields missing. That made send-readiness vulnerable to
ambiguous blocked/would-send rows before real Telegram sends.
**Changes:**
- Delivery rows now persist explicit `delivery_mode`, `delivery_state`,
  `status_detail`, `send_guard_enabled`, `would_send`, `sent`, and `failed`
  fields while keeping legacy `state` compatibility.
- Artifact doctor and send-readiness now block fresh/latest-run rows with
  missing or contradictory delivery status fields, while legacy rows remain
  readable and can be audited separately.
- Added a compact `--event-alpha-burn-in-review` inbox view for phone-friendly
  burn-in triage, plus `BURN_IN_REVIEW=1 make event-alpha-notification-inbox`.
- Added the explicit
  `make event-alpha-notify-llm-deep-real-no-send-rehearsal-with-fixture-candidate`
  alias and tightened fast-rehearsal caps for catalyst search/source
  enrichment/LLM/evidence acquisition.
**Verify:** `python3 tests/test_indicators.py` passed (558/558). Full Make
verification is run after this doc update before commit/push.
**Notes/risks:** Research-only artifact/readiness work. No Telegram sends in
tests, no trades, no paper trades, no normal RSI rows, and no LLM/provider path
can create `TRIGGERED_FADE`.

## 2026-06-29 — Make notify_llm_deep rehearsal previews portable · Codex
**Why:** The real `notify_llm_deep` no-send rehearsal could write delivery rows
with a stale machine-specific `/Users/...` preview path and no portable
`notification_preview_relpath`, causing send-readiness to fail in another
checkout. The heartbeat preview also still under-reported extraction rows, LLM
calls/skips, and due/blocked lane counts in some blocked no-send paths.
**Changes:**
- Delivery rows now persist `notification_preview_relpath` alongside legacy
  absolute preview paths, and send-readiness/artifact-doctor resolution uses
  relpath first, namespace default preview second, and absolute path only as a
  fallback.
- Send-readiness reports `notification_preview_path_resolved` plus
  `notification_preview_path_source`, and no longer blocks on a stale absolute
  path when the namespace-relative/default preview exists.
- Heartbeat previews now render latest-run extraction rows, alert counts, LLM
  calls/skips, heartbeat due/sent state, and detailed due/sent/guard-blocked/
  quality/cooldown/not-due lane counts from the run/plan summary.
- Artifact doctor strict checks now catch missing preview relpaths,
  unresolvable previews, LLM summary mismatches, lane-count mismatches, and
  missing send-guard status. Added a capped
  `event-alpha-notify-llm-deep-real-no-send-rehearsal-fast` target for quicker
  preview/readiness proof.
**Verify:** `python3 tests/test_indicators.py` passed (553/553). Full Make
verification list for this prompt was run after docs: `make
event-alpha-signal-quality-eval PYTHON=python3`, `make
event-alpha-notification-format-smoke PYTHON=python3`, `make
event-alpha-notify-llm-deep-no-send-smoke PYTHON=python3`, `make
event-alpha-send-readiness PROFILE=notify_llm_deep_no_send_smoke PYTHON=python3`,
`make event-alpha-live-burn-in-no-send PYTHON=python3`, `make
event-alpha-evidence-acquisition-smoke PYTHON=python3`, `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`, and `make verify
PYTHON=python3`. Manual smoke also ran the fast deep no-send rehearsal,
send-readiness, strict artifact doctor, and inbox for the rehearsal namespace.
**Notes/risks:** This is preview/readiness artifact hardening only. It does not
send Telegram in tests, trade, paper trade, write normal RSI rows, or create
`TRIGGERED_FADE`.

## 2026-06-29 — Finish notify_llm_deep rehearsal readiness gate · Codex
**Why:** The deep notification rehearsal preview could contradict the real run
ledger (`Raw events=0`, `Core opportunities=0`, `Completed=no`) even after a
successful run, and no final artifact gate existed to stop real Telegram sends
when preview/delivery/core artifacts were stale or unclear.
**Changes:**
- Heartbeat and no-digest notification previews now use the latest run summary
  and canonical core counts, include extraction rows, alertable decisions,
  delivery lane counts, provider issue counts, LLM call/skip counts, artifact
  doctor status, and explicit no-send/send-guard wording.
- Blocked delivery previews/reports distinguish `would_send_but_guard_disabled`,
  send-guard blocks, quality-gate blocks, cooldown blocks, and not-due lanes.
- Artifact doctor now checks preview/run summary consistency, core-count
  consistency, alertable-count consistency, and missing/unclear send guard
  status in strict mode.
- Added `event_alpha_send_readiness.py`, CLI/Make wiring, and a repeatable
  no-send deterministic `notify_llm_deep` fixture rehearsal. The readiness gate
  requires a completed latest run, strict doctor with no blockers, a matching
  preview, canonical delivery identity, confirmation for alertable cores, and
  clear Telegram/send-guard state.
- Bounded catalyst-frame LLM calls by the notification runtime deadline so a
  slow read cannot hang the rest of the rehearsal.
**Verify:** `python3 tests/test_indicators.py` passed (550/550);
`make event-alpha-signal-quality-eval PYTHON=python3`, `make
event-alpha-notification-format-smoke PYTHON=python3`, `make
event-alpha-notify-llm-deep-no-send-smoke PYTHON=python3`, `make
event-alpha-notify-llm-deep-rehearsal-with-fixture-candidate PYTHON=python3`,
`make event-alpha-notify-llm-deep-real-no-send-rehearsal PYTHON=python3`,
`make event-alpha-send-readiness PROFILE=notify_llm_deep_rehearsal
PYTHON=python3`, `make event-alpha-live-burn-in-no-send PYTHON=python3`,
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`, `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`, `make
event-alpha-daily-brief PROFILE=notify_llm_deep_rehearsal PYTHON=python3`,
`make event-alpha-notification-inbox PROFILE=notify_llm_deep_rehearsal
PYTHON=python3`, `make event-alpha-artifact-doctor
PROFILE=notify_llm_deep_rehearsal STRICT=1 PYTHON=python3`, and `make verify
PYTHON=python3` all passed. The real deep rehearsal ended with no send-readiness
blockers and `READY_FOR_NO_SEND_REHEARSAL_REVIEW: yes`.
**Notes/risks:** This is artifact, preview, and readiness hardening only. It
does not send Telegram during tests, trade, paper trade, write normal RSI rows,
or create `TRIGGERED_FADE`. Provider warnings from GDELT/RSS/CryptoPanic remain
fail-soft live-source noise.

## 2026-06-29 — Add real notify_llm_deep no-send rehearsal · Codex
**Why:** Fixture notification smokes were green, but old real-profile
`notify_llm_deep` delivery rows could still look like current blockers. The
operator needs a fresh real-profile no-send rehearsal that writes the same
artifacts as a scheduled run without contacting Telegram, plus doctor output
that separates latest-run safety from stale legacy rows.
**Changes:**
- Added `make event-alpha-notify-llm-deep-real-no-send-rehearsal`, which runs
  the actual `notify_llm_deep` profile with `--event-alert-send` while forcing
  `RSI_EVENT_ALERTS_ENABLED=0`, then writes/prints daily brief, inbox,
  deliveries report, and strict artifact doctor output under the
  `notify_llm_deep_rehearsal` namespace.
- Notification delivery now writes `event_alpha_notification_preview.md` even
  when a guarded rehearsal has no digest candidates, with a concise no-send
  preview instead of an empty/missing preview file.
- Artifact doctor delivery checks now report `latest_run_id`,
  latest/stale/legacy delivery-row counts, stale/legacy missing-core identity
  counters, and a configurable delivery strict scope (`latest_run` by default
  when a latest run is available; `all_rows` for migration sweeps).
- Added regression tests for no-candidate previews, latest-run delivery scoping,
  and the real no-send rehearsal Make target guard.
**Verify:** `python3 tests/test_indicators.py` passed (545/545);
`python3 -m compileall -q crypto_rsi_scanner tests` passed; `make
event-alpha-signal-quality-eval PYTHON=python3`, `make
event-alpha-notification-format-smoke PYTHON=python3`, `make
event-alpha-notify-llm-deep-no-send-smoke PYTHON=python3`, `make
event-alpha-live-burn-in-no-send PYTHON=python3`, `make
event-alpha-evidence-acquisition-smoke PYTHON=python3`, `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`, and `make verify
PYTHON=python3` all passed. The real `notify_llm_deep` rehearsal wrote 122
visible core opportunities and 122/122 card coverage, had zero alertable
research decisions, recorded one heartbeat would-send item blocked by
`RSI_EVENT_ALERTS_ENABLED=0`, and strict artifact doctor reported no blockers.
**Notes/risks:** This is notification artifact and operator UX hardening only.
It does not send Telegram unless the existing send guard is explicitly enabled,
and it does not change Event Alpha scoring, trading, paper trading, normal RSI
rows, or `TRIGGERED_FADE` rules.

## 2026-06-29 — Enforce canonical notification delivery identity · Codex
**Why:** A live-style daily digest delivery could still be recorded with a
lower-level hypothesis/watchlist id and no `core_opportunity_id`, feedback
target, or canonical card path. That made the inbox/audit path look like a
different opportunity than the actual core row, and artifact doctor did not
catch it.
**Changes:**
- Notification previews now keep one section per lane in
  `event_alpha_notification_preview.md` instead of overwriting the file with
  only the last lane.
- Daily digest and instant-escalation delivery rows are now doctor-checked for
  canonical core identity, feedback target, canonical card path, and canonical
  alert id. Heartbeats and explicit legacy/external rows remain exempt.
- Delivery-time confirmation guards now also block unconfirmed BTC/ETH/SOL
  broad strategic/treasury/valuation context from digest promotion.
- The fixture notification smoke now writes VELVET accepted high-priority,
  AAVE accepted digest, and BTC/TAO rejected control core rows, and the new
  `make event-alpha-notify-llm-deep-no-send-smoke` proves blocked would-send
  delivery rows without Telegram.
**Verify:** `python3 tests/test_indicators.py` passed (543/543). Also ran
targeted notification regression tests, `make
event-alpha-notify-llm-deep-no-send-smoke PYTHON=python3`, strict artifact
doctor on that no-send namespace, `make event-alpha-signal-quality-eval
PYTHON=python3`, `make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`,
`make event-alpha-quality-validation-cycle PYTHON=python3`, `make
event-llm-eval PYTHON=python3`, `make event-llm-extract-eval PYTHON=python3`,
`make event-alpha-eval PYTHON=python3`, and `make verify PYTHON=python3`. The
no-send smoke wrote two blocked would-send rows with canonical `agg:...`
identity, no fake sender delivery, and artifact doctor status `OK`.
**Notes/risks:** This is notification artifact/UX hardening only. No trading,
paper trading, normal RSI signal writes, or LLM-created `TRIGGERED_FADE` paths
were added.

## 2026-06-28 — Harden live notification identity and broad-asset digest guards · Codex
**Why:** A live-style notification artifact could still be misleading if a
delivery used a lower-level source row identity, or if a BTC/ETH/SOL
Strategy/MSTR treasury-valuation article satisfied "strong direct source"
confirmation without accepted evidence or fresh market confirmation.
**Changes:**
- The notification-format smoke now writes canonical CoreOpportunity rows,
  research cards, alert snapshots, delivery ledger rows, and a Telegram preview
  from a core-backed VELVET/SpaceX opportunity plus a weak BTC strategic-context
  control that remains local-only.
- Fixture snapshots now preserve canonical evidence counts after core-store
  normalization (`accepted_evidence_count` falls back to
  `evidence_acquisition_accepted_count`).
- Live confirmation now rejects broad BTC/ETH/SOL strategic/valuation/treasury
  context such as Strategy/MSTR valuation, ETF/company-equity valuation, or
  market-structure commentary unless accepted evidence, official/tagged source
  evidence, direct token impact, or fresh non-generic market confirmation exists.
- Artifact doctor now reports `strategic_broad_asset_digest_without_confirmation`
  for delivered/promoted daily digests that violate that guard.
**Verify:** `python3 tests/test_indicators.py` passed (541/541). Also ran
`make event-alpha-signal-quality-eval PYTHON=python3`, `make
event-alpha-notification-format-smoke PYTHON=python3`, `make
event-alpha-live-burn-in-no-send PYTHON=python3`, `make
event-alpha-burn-in-readiness PROFILE=live_burn_in_no_send PYTHON=python3`,
strict `make event-alpha-artifact-doctor PROFILE=live_burn_in_no_send STRICT=1
PYTHON=python3`, `make event-alpha-evidence-acquisition-smoke PYTHON=python3`,
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`, notification-format
inbox/daily-brief/opportunity-audit manual checks, and `make verify
PYTHON=python3`.
**Notes/risks:** Live burn-in remains no-send and research-only. The run
completed with expected provider noise (GDELT 429, RSS 403, OpenAI extraction
timeouts) and no doctor blockers; live namespace warnings remain review
diagnostics rather than notification identity/digest blockers.

## 2026-06-28 — Harden live burn-in acquisition and readiness · Codex
**Why:** `event-alpha-live-burn-in-no-send` could still crash when evidence
acquisition exited early or provider calls failed, and older/carded artifacts
could make doctor/readiness reports look worse than the canonical core review
surface actually was.
**Changes:**
- Evidence acquisition run results now always include `results`, `status`, path,
  and warnings for disabled, no-candidate, provider-unavailable, skipped-budget,
  failed-soft, and artifact-write-warning paths.
- Event Alpha run ledgers persist `evidence_acquisition_run_status` so live
  burn-in reports can distinguish no-candidate/disabled/failed-soft acquisition
  runs from missing artifacts.
- Artifact doctor now treats research-card metadata as a valid card-path mapping
  for legacy core rows whose stored `card_path` was not backfilled.
- Burn-in readiness now keys the feedback gate to visible canonical core card
  and feedback-target coverage, while still leaving full artifact doctor/audit
  checks intact.
**Verify:** `python3 tests/test_indicators.py` passed (540/540). Also ran
`make event-alpha-signal-quality-eval PYTHON=python3`, `make
event-alpha-notification-format-smoke PYTHON=python3`, `make
event-alpha-live-burn-in-no-send PYTHON=python3`, `make
event-alpha-burn-in-readiness PROFILE=live_burn_in_no_send PYTHON=python3`,
strict `make event-alpha-artifact-doctor PROFILE=live_burn_in_no_send STRICT=1
PYTHON=python3`, `make event-alpha-evidence-acquisition-smoke PYTHON=python3`,
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`, and manual
`event-alpha-daily-brief`, `event-alpha-notification-inbox`, and
`event-opportunity-audit` checks for `live_burn_in_no_send`.
**Notes/risks:** The live no-send run completed with expected provider warnings
(GDELT 429, RSS 403/backoff) and no sends. Strict doctor had no blockers; it
still reports non-blocking hygiene warnings for weak/unqualified incident links.

## 2026-06-28 — Canonicalize Event Alpha notification delivery identity · Codex
**Why:** A notify run could deliver a Telegram digest whose delivery ledger was
keyed to a lower-level hypothesis row while cards, snapshots, daily brief, and
the canonical core store showed a different opportunity. Weak live-style rows
with rejected-only evidence could also remain digest-eligible in the send path.
**Changes:**
- Event Alpha notification plans now reconcile router decisions against
  canonical CoreOpportunity rows before sending or writing delivery ledger rows.
  New delivery rows persist canonical core id, symbol/coin, card path, feedback
  target, source alert ids, notification item ids, identity reconciliation
  status, and preview path.
- Telegram digest rendering for routed Event Alpha notifications now uses a
  compact operator format with one top-level research disclaimer, top 3
  candidates, evidence/market/check-next lines, and no raw alert id/card id/full
  local path/debug dump in the Telegram body.
- Live/send digest notification gating now blocks canonical core rows whose
  evidence acquisition is `rejected_results_only`, `no_results`, `skipped_budget`,
  or otherwise non-confirming unless accepted evidence, strong official/tagged
  source evidence, or fresh non-generic market confirmation is present.
- Notification delivery previews are written to
  `event_alpha_notification_preview.md`, and artifact doctor now checks delivery
  identity/core-store mismatches, noncanonical alert ids, rejected-only digest
  sends, missing previews, absolute paths, and raw debug fields in Telegram
  previews.
- Notification inbox core-review items now display the canonical
  `core_opportunity_id` first and keep linked lower-level alert ids as
  `source_alert_id` audit metadata, so old delivered artifacts no longer read as
  if the source/support row were the primary review target.
- Added `make event-alpha-notification-format-smoke` for fake-sender
  formatting/preview/doctor smoke coverage.
**Verify:** `python3 tests/test_indicators.py` passed (539/539). Further
verification commands were run after this entry as part of the same prompt:
`make event-alpha-signal-quality-eval PYTHON=python3`, `make
event-alpha-notification-format-smoke PYTHON=python3`, `make
event-alpha-live-burn-in-no-send PYTHON=python3`, strict `make
event-alpha-artifact-doctor PROFILE=live_burn_in_no_send STRICT=1
PYTHON=python3`, `make event-alpha-evidence-acquisition-smoke PYTHON=python3`,
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`, and `make verify
PYTHON=python3`.
**Notes/risks:** Formatting and research-notification delivery only. No live
trading, paper trades, normal RSI rows, or provider/LLM-created
`TRIGGERED_FADE` paths were added. Actual Telegram delivery still requires the
existing send guard.

## 2026-06-28 — Make review surfaces core-opportunity-first · Codex
**Why:** Notification inbox, feedback readiness, and opportunity audit still
had paths that could surface diagnostic/support alert snapshots as if they were
reviewable operator opportunities, or choose a diagnostic snapshot before the
canonical core snapshot.
**Changes:**
- Notification inbox now builds canonical review items from
  `event_core_opportunities.jsonl` first, resolves cards and feedback targets to
  the core opportunity, and hides diagnostic/support snapshots by default.
- Feedback readiness counts canonical review items/cards/feedback targets
  separately from hidden diagnostics, so support rows cannot make readiness look
  worse or better than the actual operator handoff.
- Opportunity audit now prefers canonical snapshots for core reconciliation and
  reports diagnostic/support snapshots only in the diagnostics view.
- Artifact doctor gained review-surface checks for core item cards/feedback
  targets, diagnostics visible by default, and non-canonical audit primaries.
- Alert-snapshot loading keeps canonical and diagnostic snapshots for the same
  core instead of collapsing them during JSONL de-duplication.
**Verify:** `python3 tests/test_indicators.py` passed (536/536);
`make event-alpha-signal-quality-eval PYTHON=python3`; `make
event-alpha-evidence-acquisition-smoke PYTHON=python3`; strict `make
event-alpha-artifact-doctor PROFILE=evidence_acquisition_smoke STRICT=1
PYTHON=python3`; `make event-alpha-feedback-readiness
PROFILE=evidence_acquisition_smoke PYTHON=python3`; `make
event-opportunity-audit PROFILE=evidence_acquisition_smoke
TARGET=agg:3381ebd96566 PYTHON=python3`; `make
event-alpha-notification-inbox PROFILE=evidence_acquisition_smoke
PYTHON=python3`; `make event-alpha-market-refresh-smoke PYTHON=python3`; `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`; `make
event-alpha-quality-validation-cycle PYTHON=python3`; and `make verify
PYTHON=python3` all passed.
**Notes/risks:** Research-artifact presentation and readiness only. No
Telegram sends, paper trades, normal RSI rows, live DB writes, execution paths,
or non-event-fade `TRIGGERED_FADE` paths were added.

## 2026-06-28 — Keep diagnostic support snapshots non-alertable · Codex
**Why:** Diagnostic/source-noise alert snapshots could link to a high-priority
canonical CoreOpportunity for audit and then be re-promoted on load, inheriting
the canonical `HIGH_PRIORITY_RESEARCH` route while still carrying
`insufficient_data` diagnostic fields. That made alert snapshots look alertable
when only the canonical core row should be.
**Changes:**
- Added an explicit diagnostic/support snapshot reconciliation path that links
  support rows to their canonical core without inheriting route, tier,
  opportunity level, state, or alertability.
- Hardened alert-snapshot loading so persisted diagnostic/support markers
  survive the sibling core-store reconciliation pass.
- Artifact doctor now detects alertable diagnostic support rows, support rows
  inheriting canonical routes, duplicate alertable canonical snapshots, and
  missing canonical snapshots separately.
- Research-card copy no longer lets stale support-row local-only blockers leak
  into promoted core cards.
- Added regression tests for diagnostic support snapshots, loader
  reconciliation, daily brief/inbox behavior, strict doctor blockers, and
  duplicate canonical snapshot detection.
**Verify:** `python3 tests/test_indicators.py` passed (532/532);
`make event-alpha-signal-quality-eval PYTHON=python3` passed (36/36);
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`,
`make event-alpha-artifact-doctor PROFILE=evidence_acquisition_smoke STRICT=1
PYTHON=python3`, `make event-alpha-market-refresh-smoke PYTHON=python3`,
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`, and
`make event-alpha-quality-validation-cycle PYTHON=python3` completed with no
artifact-doctor blockers for the relevant strict doctors.
**Notes/risks:** Research-artifact consistency only. No Telegram sends, paper
trades, normal RSI rows, live DB writes, execution paths, or non-event-fade
`TRIGGERED_FADE` paths were added.

## 2026-06-28 — Reconcile alert snapshots with canonical core state · Codex
**Why:** Live/no-send artifacts could have canonical CoreOpportunity rows capped
to exploratory/local after live confirmation gates while linked
`event_alpha_alerts.jsonl` snapshots still displayed stale pre-cap
`validated_digest` / `RESEARCH_DIGEST` state. That made inbox, feedback, daily
brief, and doctor output disagree about whether CHZ/ARG-style rows were
alertable.
**Changes:**
- Added alert-snapshot reconciliation helpers that mirror final route, tier,
  opportunity level, state, live-confirmation, evidence-acquisition,
  feedback-target, and alertability fields from canonical core-store rows.
- `load_alert_snapshots()` now reconciles against sibling
  `event_core_opportunities.jsonl` automatically when present, and alertable
  snapshot filtering uses the reconciled final route.
- Daily brief alertable counts, notification inbox queues, feedback readiness,
  opportunity audit, and artifact doctor now expose or enforce snapshot/core
  reconciliation state.
- Artifact doctor strict mode blocks fresh unreconciled snapshot/core route,
  level, live-confirmation, or missing-core mismatches while treating
  pre-reconciliation alertability as an audit warning once reconciled.
- Added regression tests for stale digest snapshots, sibling core-store loading,
  inbox/readiness/daily-brief counts, doctor blockers, and audit explanation.
**Verify:** `python3 tests/test_indicators.py` passed (530/530);
`make event-alpha-signal-quality-eval PYTHON=python3` passed (36/36);
`make event-alpha-evidence-acquisition-smoke PYTHON=python3`,
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`, and
`make event-alpha-live-burn-in-no-send PYTHON=python3` completed; live burn-in
strict doctor reported zero snapshot/core mismatches and no blockers; `make
verify PYTHON=python3` passed.
**Notes/risks:** Research-artifact consistency only. No Telegram sends, paper
trades, normal RSI rows, live DB writes, execution paths, or non-event-fade
`TRIGGERED_FADE` paths were added.

## 2026-06-28 — Require live confirmation for Event Alpha digest promotion · Codex
**Why:** Fresh `live_burn_in_no_send` artifacts still promoted weak
`validated_digest` candidates when source-pack evidence acquisition was skipped,
found no results, or found only rejected evidence. Live-style burn-in needs real
confirmation before digest/watchlist/high-priority rows are operator-visible as
promoted opportunities.
**Changes:**
- Added profile-aware live confirmation policy for canonical core writes:
  live/no-send/research-send style profiles cap digest-or-higher rows unless
  they have accepted source-pack evidence, official/structured source evidence,
  matching CryptoPanic token/catalyst evidence, strong direct source evidence,
  or fresh non-generic market confirmation.
- Evidence acquisition statuses now persist confirmation semantics:
  `confirms`, `does_not_confirm`, `unresolved`, or `coverage_gap`, with
  `acquisition_confirms_candidate` and `acquisition_confirms_impact_path`.
- Sector-only rows are capped below digest by default via
  `RSI_EVENT_ALPHA_ALLOW_SECTOR_DIGEST=0`.
- Daily brief and quality review now show live-confirmation-gated candidates and
  counts for rejected-only, skipped-budget, no-results, and sector caps.
- Artifact doctor strict mode now blocks live promoted core rows without
  confirmation via live confirmation counters.
- Added regression tests for skipped-budget, rejected-only, sector-only,
  accepted CryptoPanic evidence, official exchange evidence, report visibility,
  and doctor blockers.
**Verify:** `python3 tests/test_indicators.py` passed (526/526).
**Notes/risks:** Research-artifact gating only. No Telegram sends, paper
trades, normal RSI rows, live DB writes, execution paths, or non-event-fade
`TRIGGERED_FADE` paths were added.

## 2026-06-28 — Repair canonical core route truth · Codex
**Why:** A fresh live-style no-send audit found five canonical
CoreOpportunity rows whose final opportunity verdict was `validated_digest`
while the persisted final route still said `STORE_ONLY`. That made operator
artifacts undercount digest opportunities even though fixture doctors were
green.
**Changes:**
- Canonical core-store writes now derive `final_route_after_quality_gate`,
  `route`, and `tier` from the final opportunity level when no quality block,
  quality cap, suppression, or triggered-fade route applies.
- Added a `canonical_route_adjustment_reason` and normalized final verdict copy
  when stale primary-row local-only text conflicts with the final core route.
- Extended artifact doctor strict checks with
  `core_route_conflicts_with_opportunity_level`, which blocks fresh core rows
  that persist digest/watchlist/high-priority verdicts as local/store-only
  routes without a real gate.
- Added regressions for route derivation and doctor conflict detection.
- Regenerated catalyst-frame, evidence-acquisition, market-refresh,
  quality-validation, and live no-send burn-in artifacts for review.
**Verify:** `python3 tests/test_indicators.py` passed (522/522); regenerated
all audit profiles; all profile reports ran; strict doctors for
`catalyst_frame_e2e`, `evidence_acquisition_smoke`, `market_refresh_smoke`,
`quality_validation`, and `live_burn_in_no_send` report
`core_route_conflicts_with_opportunity_level=0`; direct JSONL/card inspection
found no route/verdict mismatches, duplicate core ids, missing cards, or raw
watchlist quality conflicts. Final verification also ran
`make event-llm-eval PYTHON=python3`, `make event-llm-extract-eval
PYTHON=python3`, `make event-alpha-eval PYTHON=python3`, `make
event-alpha-signal-quality-eval PYTHON=python3`, and `make verify
PYTHON=python3`.
**Notes/risks:** Research-artifact repair only. No Telegram sends, paper
trades, normal RSI rows, live DB writes, execution paths, or non-event-fade
`TRIGGERED_FADE` paths were added. Live burn-in still shows expected fail-soft
public-provider warnings such as GDELT 429 and RSS 403.

## 2026-06-28 — Add live-style Event Alpha no-send burn-in gate · Codex
**Why:** Event Alpha needed a real live-style, no-send proof path before any
notification promotion: provider gaps, source-pack coverage, cards, feedback
targets, market freshness, evidence acquisition, and artifact hygiene must be
visible in one operator flow without sending Telegram or touching trading paths.
**Changes:**
- Added the `live_burn_in_no_send` profile and Make targets for
  `event-alpha-live-burn-in-no-send` and `event-alpha-burn-in-readiness`.
- Added `event_alpha_burn_in_readiness.py` plus scanner CLI wiring for a
  profile-aware readiness gate that confirms a successful latest run,
  no-send/no-delivery status, provider coverage, evidence acquisition, market
  freshness visibility, feedback readiness, and strict artifact-doctor status.
- Expanded provider status with configured/not-configured/healthy provider
  summaries and source-pack coverage gaps with evidence-absence semantics.
- Added a Burn-In Readiness section to the daily brief and a configurable
  `RSI_EVENT_RESEARCH_CARDS_WRITE_LIMIT` so burn-in profiles can write cards for
  every visible core opportunity.
- Hardened artifact-doctor card-group validation so healthy
  `QUALITY_BLOCKED`/local-only cards are not incorrectly treated as near-miss
  mismatches.
- Updated `.env.example`, `ROADMAP.md`, `DECISIONS.md`, and
  `research/EVENT_ALPHA_RUNBOOK.md`.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`;
`python3 tests/test_indicators.py` passed (520/520); `make
event-alpha-signal-quality-eval PYTHON=python3` passed (36/36); `make
event-alpha-live-burn-in-no-send PYTHON=python3` completed with no sends and
`READY_FOR_NO_SEND_BURN_IN_REVIEW: yes`; `make event-alpha-burn-in-readiness
PROFILE=live_burn_in_no_send PYTHON=python3` confirmed 70 core opportunities,
70 cards, 70 feedback targets, 10 evidence-acquisition rows, and no blockers;
`make verify PYTHON=python3` passed.
**Notes/risks:** The live-style burn-in still surfaces expected fail-soft
provider warnings such as GDELT 429s, RSS 403s, and one OpenAI extraction
timeout. These are recorded as provider/readiness signals, not crashes. No
Telegram sends, paper trades, normal RSI rows, live DB writes, execution paths,
or LLM/provider-created `TRIGGERED_FADE` were added.

## 2026-06-28 — Surface Event Alpha source contracts in artifacts · Codex
**Why:** Source Registry v2 could already classify provider quality, but
operator-facing cards/audits and evidence-acquisition rows did not consistently
show the concrete source contract: what this source can prove, cannot prove,
and which playbooks it is useful for.
**Changes:**
- Added a reusable source-contract metadata helper that merges registry
  assessment with accepted/rejected evidence rows.
- Non-official sources now explicitly list `official_confirmation` as something
  they cannot prove, so CryptoPanic/GDELT/Polymarket evidence does not look
  stronger than it is.
- Evidence acquisition artifacts now persist `source_can_prove`,
  `source_cannot_prove`, `source_useful_playbooks`,
  `evidence_absence_is_meaningful`, and source coverage gap reasons.
- Research cards and opportunity audits render compact human-readable source
  contract lines without leaking control enum names into card grouping.
- Added regressions for registry aggregation, card/audit source-contract copy,
  and acquisition artifact persistence.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`; `python3
tests/test_indicators.py` passed (516/516).
**Notes/risks:** Research-only metadata and rendering change. No sends, trades,
paper rows, normal RSI rows, or provider/LLM-created `TRIGGERED_FADE` paths
were added.

## 2026-06-28 — Join incidents into the canonical CoreOpportunity view · Codex
**Why:** Cards and audits were converging on the canonical CoreOpportunity read
model, but incident/catalyst-frame context could still be reconstructed
separately. That left room for operator-facing views to disagree about the
main incident even when the core opportunity id was stable.
**Changes:**
- `CanonicalCoreOpportunityView` now loads and exposes linked incident rows,
  including the best incident row for a core opportunity.
- Opportunity audit passes incident rows through the canonical core view and
  renders the joined incident/frame context before falling back to legacy row
  reconstruction.
- Added regressions proving VELVET/SpaceX core views and audits carry the
  joined incident frame (`proxy_attention`, main catalyst, evidence quote).
**Verify:** `python3 -m py_compile crypto_rsi_scanner/event_core_opportunity_store.py
crypto_rsi_scanner/event_opportunity_audit.py`; `python3 -m compileall -q
crypto_rsi_scanner tests`; `python3 tests/test_indicators.py` passed
(516/516, also exercised twice during focused checks); `make
event-alpha-signal-quality-eval PYTHON=python3`; `make
event-alpha-evidence-acquisition-smoke PYTHON=python3`; `make
event-alpha-market-refresh-smoke PYTHON=python3`; `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`; `make
event-alpha-quality-validation-cycle PYTHON=python3`; `make verify
PYTHON=python3`; and the requested manual evidence-acquisition audit, daily
brief, and strict artifact doctor smoke checks exited 0.
**Notes/risks:** Research-only read-model/audit change. No Telegram sends,
paper/live rows, normal RSI writes, trading, or LLM/provider-created
`TRIGGERED_FADE` paths were added.

## 2026-06-28 — Make Event Alpha core rendering verdict-aware · Codex
**Why:** Canonical CoreOpportunity rows were authoritative for route/state, but
secondary card and audit sections could still render fallback/support-row text
such as `Latest source: unknown`, `Impact path strength: unknown`, missing
market snapshots, or generic-cooccurrence blockers on a high-priority VELVET
core.
**Changes:**
- Canonical core store rows now persist derived display fields for latest
  source, source count, accepted evidence, impact-path reason/strength,
  digest eligibility, market confirmation summary/snapshot, manual verification
  items, upgrade requirements, and downgrade warnings.
- Research cards, opportunity audits, and quality-review upgrade/downgrade
  sections now use verdict-aware copy so promoted cores do not show stale
  support-row hard-gate blockers in primary sections.
- Accepted evidence samples now outrank filler/internal artifact source labels
  such as `unknown`, `impact_hypothesis`, `watchlist`, and `alert_snapshot`
  when rendering canonical latest-source fields.
- Artifact doctor now checks for canonical rendering drift, including support
  blockers in primary cards, inconsistent high-priority upgrade copy, missing
  market confirmation display, and unknown latest source despite accepted
  evidence.
- Added regressions covering VELVET canonical card fields, VELVET opportunity
  audit primary sections, quality-review verdict-aware risks, and
  artifact-doctor rendering mismatch detection.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`;
`python3 tests/test_indicators.py` passed (516/516); `make
event-alpha-signal-quality-eval PYTHON=python3`; `make
event-alpha-evidence-acquisition-smoke PYTHON=python3`; `make
event-alpha-market-refresh-smoke PYTHON=python3`; `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`; `make
event-alpha-quality-validation-cycle PYTHON=python3`; `make verify
PYTHON=python3`; and the requested manual smoke wrappers for VELVET audit,
strict evidence-acquisition artifact doctor, and daily brief all exited 0.
**Notes/risks:** Research-only artifact/presentation repair. No Telegram sends,
paper/live rows, normal RSI writes, trading, or LLM/provider-created
`TRIGGERED_FADE` paths were added.

## 2026-06-28 — Make Event Alpha core opportunity views acquisition-aware · Codex
**Why:** Evidence acquisition, cards, audits, and quality review could still
disagree after canonical core rows existed. VELVET showed accepted
CryptoPanic evidence in `event_evidence_acquisition.jsonl` while the card
displayed accepted=0, and quality review could still mix support rows into
operator sections.
**Changes:**
- Added a canonical `CoreEvidenceAcquisitionView` read model that joins core
  rows with source-pack acquisition rows, accepted/rejected samples, reason
  codes, provider failures, source pack, and before/after verdict metadata.
- Core opportunity store rows now preserve accepted evidence counts, reason
  codes, samples, source-pack status, and final acquisition metadata so cards
  and audits render from canonical core data instead of shallow support rows.
- Quality review now loads `event_core_opportunities.jsonl` through the
  profile artifact context and uses canonical core rows as the primary
  operator view; support/control rows are reported as diagnostics.
- Artifact doctor now checks card/source-pack/acquisition consistency against
  canonical core acquisition views.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`;
`python3 tests/test_indicators.py` passed (515/515); `make
event-alpha-signal-quality-eval PYTHON=python3`; `make
event-alpha-evidence-acquisition-smoke PYTHON=python3`; `make
event-alpha-market-refresh-smoke PYTHON=python3`; `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`; `make
event-alpha-quality-validation-cycle PYTHON=python3`; `make verify
PYTHON=python3`; and the requested manual smoke wrappers for VELVET audit,
quality review, strict artifact doctor, and daily brief all exited 0.
**Notes/risks:** Research-only artifact/presentation repair. No Telegram sends,
paper/live rows, normal RSI writes, trading, or LLM/provider-created
`TRIGGERED_FADE` paths were added.

## 2026-06-28 — Audit Event Alpha artifacts and repair core-card quality copy · Codex
**Why:** The post-implementation audit needed proof that fresh Event Alpha
artifacts, reports, cards, and doctors agree end-to-end. Fresh cards exposed a
presentation bug where canonical core cards could still show stale raw-row
`local-only: not_impact_hypothesis` text inside the impact-hypothesis context
even when the final core verdict was digest/high-priority.
**Changes:**
- Research-card impact-hypothesis copy now treats canonical core opportunity
  final route/state/verdict fields as authoritative, only falling back to raw
  validated-hypothesis digest checks for non-core rows.
- Core card promotion/local-only text now reflects the final verdict instead of
  defaulting to "promoted to RADAR" for every core context block.
- Added a regression around a promoted VELVET core card with stale support-row
  data so final quality-gated route copy cannot regress.
- Ran a fresh artifact QA sweep across `catalyst_frame_e2e`,
  `evidence_acquisition_smoke`, `market_refresh_smoke`, `quality_validation`,
  and `notify_llm_quality_frame`.
**Verify:** `python3 tests/test_indicators.py` passed (513/513);
`make event-llm-eval PYTHON=python3`; `make event-llm-extract-eval
PYTHON=python3`; `make event-alpha-eval PYTHON=python3`; `make
event-alpha-signal-quality-eval PYTHON=python3`; `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`; `make
event-alpha-evidence-acquisition-smoke PYTHON=python3`; `make
event-alpha-market-refresh-smoke PYTHON=python3`; `make
event-alpha-quality-validation-cycle PYTHON=python3`; `make verify
PYTHON=python3`. Strict artifact doctors had no blockers for the audited
profiles, and a direct JSONL/Markdown invariant audit found zero remaining
issues after the card-copy fix.
**Notes/risks:** Research-only artifact/presentation repair. No Telegram sends,
paper/live rows, normal RSI writes, trading, or LLM/provider-created
`TRIGGERED_FADE` paths were added.

## 2026-06-28 — Turn Event Alpha feedback into calibration data · Codex
**Why:** Event Alpha cards and core opportunities were labelable, but feedback
rows did not consistently retain enough core/card/source/market/frame context to
analyze useful vs junk signals or export proposed signal-quality eval cases.
**Changes:**
- Feedback marking can now resolve watchlist rows, canonical core rows, alert
  snapshots, and research-card paths, then persist core id, card path, run,
  profile, namespace, hypothesis/watchlist ids, final route/lane, source pack,
  source/provider metadata, market freshness, and catalyst-frame fields.
- Calibration reports now cohort labels by impact path, role, opportunity
  level, source class/domain/pack/provider, route/lane, market confirmation,
  market freshness, and catalyst frame; proposed priors include source-pack,
  source-domain, market-confirmation, and frame cohorts.
- Outcome fill artifacts now write explicit `outcome_status` values (`filled`,
  `insufficient_market_data`, `stale_market_data`, `skipped_no_asset`) while
  remaining local-fixture/research-only.
- Signal-quality export now matches feedback by core/feedback/card/alert keys,
  exports useful/junk/watch/missed cases with expected route behavior, and
  carries source/core metadata for eval-case review.
- Missed-opportunity helpers can build manual missed rows with source URL/text,
  why-it-mattered notes, expected playbook, linked core/incident hints, and a
  diagnostic failure stage.
**Verify:** `python3 tests/test_indicators.py` passed (513/513);
`make event-alpha-signal-quality-eval PYTHON=python3`; `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`; `make
event-alpha-evidence-acquisition-smoke PYTHON=python3`; `make
event-alpha-quality-validation-cycle PYTHON=python3`; `make verify
PYTHON=python3`. Manual smoke passed: `make event-alpha-feedback-readiness
PROFILE=catalyst_frame_e2e PYTHON=python3`; `make event-feedback-useful
PROFILE=catalyst_frame_e2e FEEDBACK_TARGET=agg:3381ebd96566 PYTHON=python3`;
`make event-alpha-calibration-report PROFILE=catalyst_frame_e2e
PYTHON=python3`; `make event-alpha-export-signal-quality-cases
PROFILE=catalyst_frame_e2e PYTHON=python3`; `make event-opportunity-audit
PROFILE=catalyst_frame_e2e TARGET=agg:3381ebd96566 PYTHON=python3`.
**Notes/risks:** Research-only artifact and reporting changes. No Telegram
sends, paper/live rows, normal RSI writes, trading, or LLM/provider-created
`TRIGGERED_FADE` paths were added.

## 2026-06-28 — Harden Event Alpha source contracts and acquisition artifacts · Codex
**Why:** The source registry and source-pack layer existed, but operator
artifacts needed a sharper answer to “what does this source prove, what does it
not prove, and is absence of evidence meaningful right now?”
**Changes:**
- Extended Source Registry v2 with `market_data`, v2 mission names,
  `source_can_prove`, `source_cannot_prove`, useful playbooks, coverage-gap
  reasons, and feed-level RSS quality/quarantine metadata.
- Added explicit source-pack sufficiency criteria for validated digest,
  watchlist, and high-priority review, plus a first-class
  `protocol_business_event_pack`.
- Evidence acquisition validation now carries source-pack context, pack
  sufficiency booleans, source contract fields, coverage semantics, and
  plan/results metadata into accepted/rejected samples and JSONL rows.
- Live RSS provider records per-feed health, so a 403/quarantined feed no
  longer makes the whole RSS provider look uniformly unusable.
**Verify:** `python3 tests/test_indicators.py`; `make
event-alpha-signal-quality-eval PYTHON=python3`; `make
event-alpha-evidence-acquisition-smoke PYTHON=python3`; `make
event-alpha-market-refresh-smoke PYTHON=python3`; `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`; `make
event-alpha-quality-validation-cycle PYTHON=python3`; `make verify
PYTHON=python3`.
**Notes/risks:** Research-only evidence semantics and artifact completeness.
No Telegram sends, paper/live rows, normal RSI writes, trading, or
LLM/provider-created `TRIGGERED_FADE` paths were added.

## 2026-06-28 — Add canonical core opportunity read model · Codex
**Why:** Core rows were authoritative in practice, but cards and audits still
assembled their own partial artifact views. That left room for future drift
between the canonical `event_core_opportunities.jsonl` row and linked support,
acquisition, alert, card, and feedback artifacts.
**Changes:**
- Added `CanonicalCoreOpportunityView` plus
  `load_canonical_core_opportunity_view(...)` /
  `canonical_core_opportunity_view_from_rows(...)` in
  `event_core_opportunity_store.py`.
- The canonical view now joins the stored core row, supporting rows,
  diagnostic/control rows, evidence-acquisition rows, market-refresh evidence,
  research-card path, alert snapshots, and feedback status without mutating
  artifacts.
- Updated research-card rendering and opportunity audits to consult the
  canonical read model before falling back to legacy row aggregation.
- Added a regression that proves the view loads linked cards, alerts,
  evidence-acquisition rows, market-refresh rows, feedback, and resolves a
  legacy acquisition core id back to its canonical core.
**Verify:** `python3 tests/test_indicators.py` passed (513/513);
`make event-alpha-signal-quality-eval PYTHON=python3`, `make
event-alpha-evidence-acquisition-smoke PYTHON=python3`, `make
event-alpha-market-refresh-smoke PYTHON=python3`, `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`, `make
event-alpha-quality-validation-cycle PYTHON=python3`, and `make verify
PYTHON=python3` passed. Manual smoke: `make event-opportunity-audit
PROFILE=evidence_acquisition_smoke TARGET=agg:3381ebd96566 PYTHON=python3`,
`make event-alpha-daily-brief PROFILE=evidence_acquisition_smoke
PYTHON=python3`, and `make event-alpha-artifact-doctor
PROFILE=evidence_acquisition_smoke STRICT=1 PYTHON=python3` passed.
**Notes/risks:** Read-model and presentation consistency only. No Telegram
sends, paper/live rows, normal RSI writes, trading, or provider/LLM-created
`TRIGGERED_FADE` paths were added.

## 2026-06-28 — Reconcile canonical core rendering artifacts · Codex
**Why:** Event Alpha core-store rows were authoritative, but secondary artifacts
could still disagree after card and evidence-acquisition writes. VELVET could
be stored as high-priority while a research card or acquisition row displayed a
stale `STORE_ONLY`/orphan-core view.
**Changes:**
- Backfilled generated research-card paths and feedback targets into existing
  `event_core_opportunities.jsonl` rows instead of appending duplicate core
  rows.
- Reconciled source-pack evidence-acquisition rows to compatible canonical
  core opportunity ids, preserving original ids as diagnostic metadata.
- Made research-card rendering, opportunity audit, near-miss filtering, daily
  brief freshness summaries, and artifact doctor checks prefer the reconciled
  canonical core row before support/control rows.
- Fixed canonical core market-context persistence so refreshed nested market
  snapshots override stale top-level `missing` aliases.
- Added regressions for canonical card fields, evidence-acquisition core-id
  reconciliation, artifact-doctor mismatch detection, and refreshed nested
  market context.
**Verify:** `python3 tests/test_indicators.py` passed (512/512);
`make event-alpha-signal-quality-eval PYTHON=python3`, `make
event-alpha-evidence-acquisition-smoke PYTHON=python3`, `make
event-alpha-market-refresh-smoke PYTHON=python3`, `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`, `make
event-alpha-quality-validation-cycle PYTHON=python3`, and `make verify
PYTHON=python3` passed. Manual smoke: `make event-opportunity-audit
PROFILE=evidence_acquisition_smoke TARGET=agg:3381ebd96566 PYTHON=python3`,
`make event-alpha-daily-brief PROFILE=evidence_acquisition_smoke
PYTHON=python3`, and `make event-alpha-artifact-doctor
PROFILE=evidence_acquisition_smoke STRICT=1 PYTHON=python3` passed with no
blockers.
**Notes/risks:** Research-only artifact consistency change. No Telegram sends,
paper/live rows, normal RSI writes, trading, or provider/LLM-created
`TRIGGERED_FADE` paths were added.

## 2026-06-28 — Make canonical core rows authoritative for cards and snapshots · Codex
**Why:** Event Alpha was writing `event_core_opportunities.jsonl`, but research
cards, daily-brief card groups, and alert snapshots could still create
opportunity-like IDs outside the canonical core store. Source-noise/control
snapshots also looked like separate core opportunities instead of diagnostic
support.
**Changes:**
- Added canonical core-id resolution for rows, cards, alerts, and audits:
  exact store match, compatible incident/asset/path match, diagnostic support,
  orphan, legacy, and no-core statuses.
- Made store-backed research card generation use canonical core rows directly,
  preserve catalyst-frame metadata, and share card-index grouping with daily
  briefs.
- Linked source-noise/control alert snapshots as diagnostic support rows with
  `diagnostic_row_id`, `diagnostic_support_for_core_opportunity_id`,
  `is_diagnostic_snapshot`, and core-id status metadata instead of fake visible
  core ids.
- Extended artifact doctor checks for missing core-store rows, orphan core
  cards, fake diagnostic core ids, snapshot/store mismatches, and daily
  brief/index group mismatches.
- Split daily-brief market freshness into core freshness versus support-row
  gaps, and separated evidence plans created from acquisition requests executed.
**Verify:** `python3 tests/test_indicators.py` passed (508/508);
`make event-alpha-signal-quality-eval PYTHON=python3`, `make
event-alpha-evidence-acquisition-smoke PYTHON=python3`, `make
event-alpha-market-refresh-smoke PYTHON=python3`, `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`, `make
event-alpha-quality-validation-cycle PYTHON=python3`, and `make verify
PYTHON=python3` passed. Manual smoke: `make event-alpha-daily-brief
PROFILE=evidence_acquisition_smoke PYTHON=python3`, `make
event-alpha-artifact-doctor PROFILE=evidence_acquisition_smoke STRICT=1
PYTHON=python3`, `make event-opportunity-audit
PROFILE=evidence_acquisition_smoke TARGET=core_5f5ac4e47f96 PYTHON=python3`,
and `make event-opportunity-audit PROFILE=evidence_acquisition_smoke
TARGET=agg:3381ebd96566 PYTHON=python3` passed.
**Notes/risks:** Research-only artifact consistency change. No Telegram sends,
paper/live rows, normal RSI writes, trading, or provider/LLM-created
`TRIGGERED_FADE` paths were added.

## 2026-06-28 — Persist canonical Event Alpha core opportunities · Codex
**Why:** Daily brief, near-miss, cards, audit, and doctor paths could still
recompute operator-facing opportunities from mixed raw/support rows and disagree
after market refresh or evidence acquisition. VELVET-style high-priority cores
could therefore reappear as near-miss/diagnostic rows, and RUNE-style watchlist
cores could look downgraded by stale support rows.
**Changes:**
- Added `event_core_opportunity_store.py`, a profile-scoped JSONL store for one
  canonical post-refresh `CoreOpportunity` row per visible operator opportunity.
- Wired Event Alpha cycles, run ledgers, daily briefs, near-miss reports,
  research-card inputs, opportunity audits, artifact context, and artifact
  doctor checks to prefer canonical core rows when present.
- Added deterministic final-merge/store metadata for initial, post-refresh, and
  final opportunity verdicts; market/evidence before/after fields; card path;
  feedback target; support/diagnostic row ids; and hidden diagnostic counts.
- Made stored core rows rank ahead of raw/support rows during aggregation, while
  keeping test/legacy missing-store cases as warnings instead of strict blockers.
- Added offline regressions proving VELVET/AAVE/RUNE/MEME canonical rows,
  promoted-core near-miss exclusion, daily brief store preference, and doctor
  store coverage reporting.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner/event_core_opportunity_store.py crypto_rsi_scanner/event_alpha_daily_brief.py crypto_rsi_scanner/event_alpha_artifact_doctor.py crypto_rsi_scanner/event_core_opportunities.py crypto_rsi_scanner/scanner.py tests/test_indicators.py` passed; `python3 tests/test_indicators.py` passed (502/502); `make event-alpha-signal-quality-eval PYTHON=python3`, `make event-alpha-evidence-acquisition-smoke PYTHON=python3`, `make event-alpha-market-refresh-smoke PYTHON=python3`, `make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`, `make event-alpha-quality-validation-cycle PYTHON=python3`, and `make verify PYTHON=python3` passed. Manual smoke: `make event-alpha-near-miss-report PROFILE=market_refresh_smoke PYTHON=python3` showed `near_misses=0` / `upgrade_candidates=0` with 5 canonical core rows; `make event-alpha-daily-brief PROFILE=market_refresh_smoke PYTHON=python3` wrote the brief; `make event-opportunity-audit PROFILE=market_refresh_smoke TARGET=agg:3381ebd96566 PYTHON=python3` resolved VELVET as a high-priority core opportunity; `make event-alpha-artifact-doctor PROFILE=market_refresh_smoke STRICT=1 PYTHON=python3` completed with no blockers and `visible_core_opportunities_missing_store_rows=0`.
**Notes/risks:** Research-only artifact/presentation change. No Telegram sends,
paper/live rows, normal RSI writes, trading, or provider/LLM-created
`TRIGGERED_FADE` paths were added.

## 2026-06-28 — Make evidence acquisition final-verdict consistent · Codex
**Why:** Source-pack evidence acquisition could improve evidence quality while
operator reports still described the result through a single upgrade flag, which
blurred evidence wins with actual opportunity promotion. Market-refresh and
acquisition rows also needed one canonical final verdict while keeping market
freshness separate from market reaction.
**Changes:**
- Added canonical acquisition verdict metadata: `initial_*`,
  `post_refresh_*`, `final_opportunity_*`, `final_verdict_source/reason`,
  evidence-quality deltas, final upgrade status, market freshness, and market
  reaction confirmation.
- Made final upgrade status compare the canonical final opportunity verdict,
  preserving a stronger prior market-refresh verdict when later evidence
  acquisition does not improve the opportunity.
- Updated daily briefs, research cards, opportunity audits, quality-field
  aliases, and acquisition reports to show evidence status separately from final
  verdict status.
- Added core-opportunity/source-pack dedupe for acquisition requests and a
  `strategic_investment_pack` for stake/acquisition/valuation-style events.
- Added regressions for final-verdict preservation, supporting-row dedupe, and
  AAVE strategic-investment evidence planning.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed;
`.venv/bin/python tests/test_indicators.py` passed (498/498);
`make event-alpha-evidence-acquisition-smoke PYTHON=python3` passed;
`make event-alpha-market-refresh-smoke PYTHON=python3` passed;
`make event-alpha-signal-quality-eval PYTHON=python3` passed (36/36);
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed with no
doctor blockers; `make event-alpha-quality-validation-cycle PYTHON=python3`
passed with no doctor blockers; `make verify PYTHON=python3` passed.
**Notes/risks:** Research-only. No Telegram sends, paper/live rows, normal RSI
writes, trading, or provider/LLM-created `TRIGGERED_FADE` paths were added.

## 2026-06-28 — Execute Event Alpha source-pack evidence plans · Codex
**Why:** The source registry and evidence planner could tell operators what to
search next, but daily briefs still showed mostly `planned` acquisition rows.
Event Alpha needed a safe fixture-first loop that actually runs those targeted
source-pack queries, validates evidence, records before/after quality, and
surfaces accepted/rejected/no-result outcomes.
**Changes:**
- Added `event_evidence_acquisition.py`, a research-only executor with bounded
  source-pack requests, provider dispatch, accepted/rejected evidence
  validation, before/after quality/opportunity metadata, JSONL artifact writes,
  and no send/trade/paper/normal-RSI/trigger side effects.
- Wired evidence acquisition into Event Alpha cycles, profiles, artifact
  context, run ledgers, daily briefs, research cards, opportunity audits, and
  scanner runtime provider setup.
- Added fixture search results and `make event-alpha-evidence-acquisition-smoke`
  to prove VELVET/RUNE/ZEC accepted evidence plus context-only/no-result cases.
- Added acquisition source-pack and accepted-reason metadata to feedback rows
  and calibration grouping for later source-reliability review.
- Documented the new env knobs, runbook flow, roadmap status, and durable
  research-only decision.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed;
`python3 tests/test_indicators.py` passed (496/496);
`make event-alpha-signal-quality-eval PYTHON=python3` passed (36/36);
`make event-alpha-evidence-acquisition-smoke PYTHON=python3` passed with
accepted VELVET/RUNE/ZEC evidence and no sends/trades/paper/live RSI rows;
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed with no
doctor blockers; `make event-alpha-quality-validation-cycle PYTHON=python3`
passed with no doctor blockers; `make verify PYTHON=python3` passed.
**Notes/risks:** Research-only. Source-pack acquisition can improve local
research verdicts only through deterministic validation; it cannot create
`TRIGGERED_FADE`, which remains limited to `event_fade.py` plus `proxy_fade`.

## 2026-06-28 — Add Event Alpha source registry and evidence planning · Codex
**Why:** Event Alpha needed a stronger data/news evidence layer so broad sources
like GDELT, Polymarket, and RSS can collect context without being treated as
token-identity or impact-path proof. Near-miss and operator reports also needed
to say which source pack would upgrade or downgrade a candidate.
**Changes:**
- Added `event_source_registry.py` with source classes, source missions,
  provider coverage semantics, evidence-absence rules, CryptoPanic tag matching,
  feed health/quarantine metadata, and conservative quality caps.
- Added `event_source_packs.py` for listing, perp listing, unlock, proxy
  pre-IPO/RWA, AI IPO proxy, security shock, fan/sports, political meme, and
  market-anomaly evidence packs.
- Added `event_llm_evidence_planner.py`, a deterministic/constrained evidence
  planner that produces source-pack query/checklist metadata only.
- Preserved richer provider metadata from CryptoPanic/news rows and official
  exchange announcements without changing discovery eligibility or routing.
- Threaded source-pack, provider coverage, evidence-acquisition plan, and
  coverage-gap metadata through near-miss reports, daily briefs, research cards,
  and opportunity audits.
- Added offline tests for registry/provider semantics, source packs/feed
  coverage, planner fixture cases, near-miss acquisition metadata, and operator
  surfaces.
**Verify:** `python3 tests/test_indicators.py` passed (493/493);
`python3 -m compileall -q crypto_rsi_scanner tests` passed; `git diff --check`
passed; `make event-alpha-signal-quality-eval PYTHON=python3` passed (36/36);
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed with no
doctor blockers; `make event-alpha-quality-validation-cycle PYTHON=python3`
passed with no doctor blockers; `make verify PYTHON=python3` passed.
**Notes/risks:** Research-only metadata/reporting. No Telegram sends, paper/live
rows, normal RSI writes, trading, or provider/LLM-created `TRIGGERED_FADE` paths
were added.

## 2026-06-28 — Make CoreOpportunity the Event Alpha operator artifact spine · Codex
**Why:** `market_refresh_smoke` could show a visible RUNE watchlist core
opportunity without a research card, snapshots lacked core-opportunity linkage,
near-miss output mixed already-validated upgrade candidates with local
near-misses, and artifact doctor/readiness did not enforce visible core
coverage.
**Changes:**
- Added shared visible-core helpers and row-key candidates in
  `event_core_opportunities.py`, preserving explicit aggregate ids when present.
- Research card writing now covers every visible core opportunity, including
  duplicate-suppressed rows and visible hypothesis-only cores, while preserving
  diagnostics/source-noise rows outside the main operator card set.
- Alert snapshots and card lookup now carry/link `core_opportunity_id`,
  `feedback_target`, `feedback_target_type`, card path, and card group where
  available.
- Feedback readiness and artifact doctor now report/block missing visible-core
  card/feedback coverage and missing snapshot linkage on fresh rows.
- Near-miss reporting and daily briefs now split true local near-misses from
  already-validated upgrade candidates, and market freshness readiness is
  summarized by core opportunity in default operator output.
- Updated ROADMAP, DECISIONS, and the Event Alpha runbook with the durable
  core-opportunity coverage contract.
**Verify:** `python3 tests/test_indicators.py` passed (489/489);
`make event-alpha-signal-quality-eval PYTHON=python3` passed (36/36);
`make event-alpha-market-refresh-smoke PYTHON=python3` passed and refreshed
`market_refresh_smoke` with 6 cards plus zero visible-core coverage blockers;
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed with 6
cards and strict doctor no blockers; `make event-alpha-quality-validation-cycle
PYTHON=python3` passed with strict doctor no blockers; `make verify
PYTHON=python3` passed; `python3 -m compileall -q crypto_rsi_scanner tests`
passed; manual `market_refresh_smoke` readiness, strict doctor, near-miss
report, and RUNE `core_08d464045bca` opportunity audit all passed.
**Notes/risks:** Research-only artifact/report/card linkage. No Telegram send,
paper/live rows, normal RSI writes, trading, or provider/LLM-created
`TRIGGERED_FADE` paths were added.

## 2026-06-27 — Separate Event Alpha state caps from route gates · Codex
**Why:** Targeted market refresh exposed two consistency bugs: watchlist-level
opportunities capped from requested high-priority state could be routed
`STORE_ONLY` with a lifecycle cap reason, and artifact doctor treated
quality-blocked support links as incident-promoting blockers even when a
qualified primary link existed.
**Changes:**
- Router logic now treats `QUALITY_BLOCKED` rows as route-blocked, but lets
  softer lifecycle caps such as `HIGH_PRIORITY -> WATCHLIST` continue through
  normal route eligibility and quality-route caps.
- Artifact doctor now reports `quality_blocked_links_present` separately from
  `quality_blocked_links_promoting_incident`; strict mode blocks only when a
  quality-blocked link is the only active/linked incident support, not when it
  is diagnostic support beside a qualified link.
- Near-miss and targeted-market-refresh ids now derive from canonical core
  opportunity ids when available, so duplicate/support rows do not expand the
  refresh queue.
- Added regression coverage for RUNE-like watchlist state caps, THORChain
  qualified-link plus blocked-support incidents, and core-level refresh
  dedupe.
**Verify:** `python3 tests/test_indicators.py` passed (488/488);
`make event-alpha-signal-quality-eval PYTHON=python3` passed (36/36);
`make event-alpha-market-refresh-smoke PYTHON=python3` passed; `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed; `make
event-alpha-quality-validation-cycle PYTHON=python3` passed; `make verify
PYTHON=python3` passed; manual smokes passed for `event-alpha-near-miss-report`,
strict `event-alpha-artifact-doctor`, and `event-opportunity-audit` on the
market-refresh profile.
**Notes/risks:** Research-only artifact/routing metadata. No send, paper, live
RSI, trading, or `TRIGGERED_FADE` creation paths were added.

## 2026-06-27 — Add Event Alpha targeted market refresh queue · Codex
**Why:** Strong Event Alpha candidates could remain validated-digest or
near-miss rows when their only blocker was stale or missing market context. The
operator view needed a bounded way to refresh already-validated assets before
final research routing.
**Changes:**
- Added explicit targeted market-refresh queue/result models and helpers in
  `event_near_miss.py`, including refresh ids, provider/error metadata,
  before/after market context, before/after opportunity verdicts, and
  refresh-upgrade status.
- Hardened near-miss eligibility so validated-digest rows blocked by stale,
  missing, or unknown market context can refresh, while already-promoted
  WATCHLIST/HIGH_PRIORITY rows with fresh context stay out of the queue.
- Persisted refresh before/after fields on impact hypotheses; cards, audits,
  daily briefs, and near-miss reports now show the targeted-refresh trail.
- Added targeted-refresh config aliases and made the live-style LLM quality/deep
  profile defaults explicit while preserving the older near-miss refresh names.
- Added `market_refresh_smoke` plus `make event-alpha-market-refresh-smoke`
  using fresh fixture market rows for VELVET/RUNE/AAVE/M so upgrades can be
  proved offline without sends.
**Verify:** `python3 tests/test_indicators.py` passed (488/488);
`make event-alpha-signal-quality-eval PYTHON=python3` passed (36/36);
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed; `make
event-alpha-market-refresh-smoke PYTHON=python3` passed and showed VELVET
upgrading from stale validated digest to high priority plus RUNE to watchlist;
`make event-alpha-quality-validation-cycle PYTHON=python3` passed; `make
event-llm-eval PYTHON=python3` passed (9/9); `make event-llm-extract-eval
PYTHON=python3` passed (7/7); `python3 -m compileall -q crypto_rsi_scanner
tests` passed; `make verify PYTHON=python3` passed.
**Notes/risks:** Research-only artifact/routing metadata. The refresh path only
rechecks already-validated assets and cannot send notifications, trade, paper
trade, write normal RSI rows, or create `TRIGGERED_FADE`.

## 2026-06-27 — Fix Event Alpha feedback readiness lineage · Codex
**Why:** The `catalyst_frame_e2e` feedback-readiness check could fail even
after the e2e artifacts were regenerated because research cards lacked current
feedback-target metadata, `index.md` could be mistaken for a card, and
opportunity audit did not read already-marked feedback rows.
**Changes:**
- Research cards now render current artifact lineage plus card path, stable
  feedback target, feedback target type, and ready-to-copy useful/junk/watch
  commands; legacy cards remain explicitly labeled as legacy lineage.
- Card indexes and daily briefs expose each card's operator group and feedback
  target, while artifact doctor and feedback readiness count real card files
  separately from `index.md`.
- Feedback readiness allows no-send/e2e namespaces to be ready from current
  cards even when no alert snapshots exist, and it blocks cards missing lineage
  or feedback targets.
- Opportunity audit now resolves card-path targets and reads feedback artifacts
  so marked useful/junk/watch status appears in the audit for the same target.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed;
`python3 tests/test_indicators.py` passed (488/488); `make
event-alpha-signal-quality-eval PYTHON=python3` passed (36/36); `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed; `make
event-alpha-quality-validation-cycle PYTHON=python3` passed; `make verify
PYTHON=python3` passed. Manual checks: `make event-alpha-feedback-readiness
PROFILE=catalyst_frame_e2e PYTHON=python3` is ready with
`cards_with_lineage=5/5` and `cards_with_feedback_target=5/5`; strict artifact
doctor reports `research_card_files=5`, `research_card_index_present=true`,
`cards_missing_lineage=0`, `cards_missing_feedback_target=0`, and no blockers;
`make event-opportunity-audit PROFILE=catalyst_frame_e2e TARGET=VELVET
PYTHON=python3` resolves the VELVET card path plus core feedback target.
**Notes/risks:** Research-only artifact/reporting/readiness work. No live
trading, paper trades, normal RSI signal writes, Telegram sends, or
provider/LLM-created `TRIGGERED_FADE` logic changed.

## 2026-06-27 — Polish Event Alpha traceability and live readiness · Codex
**Why:** Operator-facing Event Alpha artifacts needed a clearer join path from
daily brief → card → audit → feedback, plus live-style readiness checks for
catalyst-frame profiles and market freshness before Pro-model handoffs.
**Changes:**
- Added current lineage metadata to watchlist-derived rows and research cards,
  including run/profile/namespace, incident, hypothesis, watchlist, core
  opportunity, alert/snapshot/card, and source raw/event ids, while marking
  legacy cards with explicit lineage gaps.
- Made opportunity audit and feedback lookup accept the same core opportunity,
  hypothesis, incident, alert, snapshot, card, watchlist, symbol, and coin
  targets; inbox rows now surface the feedback target directly.
- Added a feedback-readiness report and Make target to check card lineage,
  feedback targets, inbox reviewability, and calibration field coverage.
- Added a canonical operator-view note plus market freshness readiness sections
  to daily briefs and quality reviews, and standardized profile/status copy for
  frame-enabled `notify_llm_quality` / `notify_llm_quality_frame` paths.
- Added `make event-alpha-quality-frame-live-smoke` as a no-send live-style
  frame/readiness proof target.
**Verify:** `python3 tests/test_indicators.py` passed (488/488);
`make event-llm-eval PYTHON=python3` passed (9/9); `make
event-llm-extract-eval PYTHON=python3` passed (7/7); `make event-alpha-eval
PYTHON=python3` passed (11/11); `make event-alpha-signal-quality-eval
PYTHON=python3` passed (36/36); `make event-alpha-catalyst-frame-e2e-cycle
PYTHON=python3` passed; `make event-alpha-quality-validation-cycle
PYTHON=python3` passed; `make verify PYTHON=python3` passed; manual no-send
smokes `make event-alpha-notify-llm-quality-frame-smoke PYTHON=python3`, `make
event-alpha-daily-brief PROFILE=catalyst_frame_e2e PYTHON=python3`, `make
event-opportunity-audit PROFILE=catalyst_frame_e2e TARGET=VELVET PYTHON=python3`,
`make event-alpha-quality-frame-live-smoke PYTHON=python3`, and `make
event-alpha-feedback-readiness PROFILE=notify_llm_quality PYTHON=python3`
passed. The live-style smoke recorded expected fail-soft public-provider
warnings (`GDELT` 429 and RSS 403/backoff) with strict doctor WARN-only and no
blockers.
**Notes/risks:** Research-only artifact/reporting/readiness work. No live
trading, paper trades, normal RSI signal writes, send-guard loosening, or
provider/LLM-created `TRIGGERED_FADE` logic changed.

## 2026-06-27 — Harden Event Alpha market-context freshness · Codex
**Why:** Event Alpha quality verdicts could treat stale or timestamp-less market
snapshots as if they were current market confirmation, and fixture/source
enrichment paths could try to fetch example fixture URLs. That made live-style
operator artifacts and Pro-model handoffs less trustworthy.
**Changes:**
- Added market-context freshness fields and reason codes across market
  confirmation, impact hypotheses, watchlist rows, alert snapshots, research
  cards, opportunity audit, daily brief, near-miss output, and signal-quality
  eval reporting.
- Added live-style freshness caps: stale, missing, or unknown-timestamp market
  context cannot by itself promote candidates to `WATCHLIST`/`HIGH_PRIORITY`;
  fixture/e2e profiles may explicitly allow stale fixture snapshots only when
  labeled `fixture_allowed_stale`.
- Added `RSI_EVENT_MARKET_CONTEXT_MAX_AGE_HOURS`,
  `RSI_EVENT_MARKET_CONTEXT_ALLOW_STALE_FIXTURE`, and
  `RSI_EVENT_MARKET_CONTEXT_STALE_CAP_LEVEL`.
- Made fixture/example source-enrichment URLs use existing fixture text with
  `fixture_text_used` instead of attempting network fetches.
- Extended signal-quality fixtures/tests for fresh VELVET market context, stale
  fixture allowance, stale live caps, missing/unknown timestamps, top-level
  watchlist quality fields, and fixture-source enrichment behavior.
- Updated `DECISIONS.md`, `ROADMAP.md`, `.env.example`, and
  `research/EVENT_ALPHA_RUNBOOK.md`.
**Verify:** `python3 tests/test_indicators.py` passed (485/485);
`make event-alpha-signal-quality-eval PYTHON=python3` passed (36/36);
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed, with strict
doctor ending WARN-only and `missing_total=0`; `make
event-alpha-quality-validation-cycle PYTHON=python3` passed, with strict doctor
WARN-only and `missing_total=0`; `make verify PYTHON=python3` passed; manual
smokes `make event-alpha-notify-llm-quality-frame-smoke PYTHON=python3`, `make
event-alpha-daily-brief PROFILE=catalyst_frame_e2e PYTHON=python3`, and `make
event-opportunity-audit PROFILE=catalyst_frame_e2e TARGET=VELVET PYTHON=python3`
passed. The exact `core_2f529afceef0` audit target did not resolve in the
current e2e artifacts because core ids are regenerated by artifact shape; symbol
fallback audited the same VELVET opportunity successfully.
**Notes/risks:** Research-only artifact/scoring hygiene. No live trading, paper
trades, normal RSI signal writes, notification send-guard changes, or
provider/LLM-created `TRIGGERED_FADE` logic changed.

## 2026-06-27 — Lock Event Alpha operator presentation fields · Codex
**Why:** The operator-facing Event Alpha reports were mostly core-first, but
reason text still lived in several modules and the signal-quality eval did not
explicitly guard brief-section, diagnostic-visibility, false-positive, or
human-readable reason output. A catalyst-frame quality review also showed that
hidden support rows could still leak into the possible-false-positive section.
**Changes:**
- Added `event_alpha_reason_text.py` as the shared translator for Event Alpha
  reason/action codes used by daily briefs, quality reviews, research cards,
  opportunity audits, and signal-quality eval output.
- Extended the signal-quality eval with `brief_section`,
  `diagnostic_visibility`, `false_positive_reason`, and
  `human_readable_reason`, and pinned key VELVET/RUNE/MemeCore/HYPE/BTC fixture
  expectations to those fields.
- Tightened research-card index content fallback so cards are not classified as
  diagnostics merely because they contain generic diagnostic wording.
- Tightened quality-review possible-false-positive filtering so promoted core
  opportunities and ordinary missing-context/local-only support rows do not
  appear suspicious unless explicit source-noise, identity collision, generic
  co-occurrence, or rejected-identity evidence exists.
- Updated `DECISIONS.md`, `ROADMAP.md`, and
  `research/EVENT_ALPHA_RUNBOOK.md` with the shared operator-presentation
  contract.
**Verify:** `python3 tests/test_indicators.py` passed (484/484); `make
event-alpha-signal-quality-eval PYTHON=python3` passed (32/32); `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed; `make
event-alpha-quality-validation-cycle PYTHON=python3` passed; `make verify
PYTHON=python3` passed; manual smokes `make event-alpha-daily-brief
PROFILE=catalyst_frame_e2e PYTHON=python3`, `make event-alpha-quality-review
PROFILE=catalyst_frame_e2e PYTHON=python3`, and `make event-opportunity-audit
PROFILE=catalyst_frame_e2e TARGET=VELVET PYTHON=python3` passed.
**Notes/risks:** Presentation/eval/docs only. No Event Alpha scoring, routing
eligibility, notification send guards, normal RSI alerting, paper/live trading,
or deterministic `TRIGGERED_FADE` logic changed.

## 2026-06-27 — Standardize review zip filename · Codex
**Why:** Repeated Pro-model handoffs had accumulated many timestamped/hash-
suffixed zip files in the repo root, which made mobile download and handoff
confusing.
**Changes:**
- Deleted the existing root-level `*.zip` handoff artifacts.
- Added `scripts/export_source_with_artifacts.py` and `make
  export-src-with-artifacts`, which overwrite one fixed review artifact:
  `crypto_rsi_scanner_source_with_artifacts.zip`.
- Updated `.gitignore` so the fixed review zip and older hyphenated
  source-with-artifacts variants remain untracked.
- Updated `AGENTS.md` so Claude and Codex should stop creating timestamped or
  hash-suffixed review zips and use the fixed overwrite-in-place filename.
**Verify:** `make export-src-with-artifacts PYTHON=python3` wrote
`crypto_rsi_scanner_source_with_artifacts.zip` with 394 entries, 183 artifact
entries, 20 research-card files, and 0 excluded entries; `python3 -m compileall
-q crypto_rsi_scanner tests scripts` passed; `python3 tests/test_indicators.py`
passed (484/484); `make verify PYTHON=python3` passed.
**Notes/risks:** Export/operational-protocol only. The zip still excludes
secrets, DBs, logs, virtualenvs, git data, caches, and other zip files while
including source plus local research artifacts such as `event_fade_cache/`.

## 2026-06-27 — Polish Event Alpha operator-facing opportunity reports · Codex
**Why:** The catalyst-frame e2e output was correct but still too noisy for an
operator: default daily briefs mixed core opportunities, near-misses,
local-only rows, raw watchlist dumps, and card links in a way that made the same
opportunity look duplicated or contradictory.
**Changes:**
- Reordered daily briefs into a core-first operator flow: executive summary,
  high-priority, validated digest, watchlist, near-miss, local/quality-capped,
  canonical incidents, system health, then a Diagnostics Appendix for raw row
  dumps and lower-level details.
- Added human-readable near-miss/local-only copy that explains what is
  interesting, what is missing, what would upgrade the candidate, and what would
  invalidate it without leaking internal reason-code strings into the main
  operator section.
- Grouped daily-brief research-card links using the same core/near-miss/local/
  diagnostic/legacy taxonomy as the card index, hiding source-noise/control
  cards from the main card list by default.
- Tightened quality-review false-positive reporting so normal
  market-dislocation rows are not flagged unless explicit source-noise,
  collision, invalid identity, or missing-impact-path suspicion evidence exists.
- Aligned notification-inbox labels and opportunity audits with the
  core-opportunity presentation model, including explicit operator-presentation
  sections for audit targets.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed;
`python3 tests/test_indicators.py` passed (484/484); `make
event-alpha-signal-quality-eval PYTHON=python3` passed (32/32); `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed; `make
event-alpha-quality-validation-cycle PYTHON=python3` passed; `make verify
PYTHON=python3` passed; manual `python3 main.py --event-opportunity-audit
VELVET --event-alpha-profile catalyst_frame_e2e
--event-alpha-artifact-namespace catalyst_frame_e2e` passed.
**Notes/risks:** Presentation/reporting-only. It does not change Event Alpha
scoring, route eligibility, send guards, normal RSI alerts, paper/live trading,
or deterministic `TRIGGERED_FADE` creation.

## 2026-06-27 — Harden Event Alpha card and diagnostics UX · Codex
**Why:** The core-opportunity output was mostly clean, but card indexes still
depended on filename hints, verdict-backed cards could fall back to generic
manual-review language, and the daily brief did not explicitly account for
hidden diagnostic/control support near the top.
**Changes:**
- Added an explicit daily-brief Diagnostics / Source-Noise / Controls section
  that reports collapsed diagnostic, source-noise, and quality-capped support
  rows without promoting them into the main opportunity list.
- Made research-card indexes use watchlist/quality metadata when cards are
  written, with content-based fallback for existing card files, so local-only,
  exploratory, diagnostic, and core cards group correctly even when filenames
  are ambiguous.
- Made research-card Playbook, Why This Matters, and Invalidation copy aware of
  validated impact path and catalyst frame status for strategic investment,
  proxy venue/exposure, and unknown market-dislocation cases.
- Expanded false-positive suspicion reason coverage for diagnostic-only and
  invalid-subject cases while continuing to keep promoted strong opportunities
  out of the false-positive list unless the row itself is a noise/collision
  diagnostic.
**Verify:** `python3 tests/test_indicators.py` passed (483/483); `python3 -m
compileall -q crypto_rsi_scanner tests` passed; `make
event-alpha-signal-quality-eval PYTHON=python3` passed (32/32); `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed; `make
event-alpha-quality-validation-cycle PYTHON=python3` passed; `make
event-alpha-notify-llm-quality-frame-smoke PYTHON=python3` passed; `make verify
PYTHON=python3` passed; manual `python3 main.py --event-opportunity-audit VELVET
--event-alpha-profile catalyst_frame_e2e --event-alpha-artifact-namespace
catalyst_frame_e2e` passed.
**Notes/risks:** Reporting/card-copy-only. It does not change Event Alpha
scoring, route eligibility, Telegram send guards, paper/live trading, normal
RSI writes, or deterministic `TRIGGERED_FADE` creation.

## 2026-06-27 — Clean Event Alpha operator output sections · Codex
**Why:** Core-opportunity aggregation was working, but daily briefs, exploratory
digests, near-miss lists, quality review, inbox text, and card indexes still
mixed promoted opportunities with raw/support/control rows in ways that made the
operator view harder to read.
**Changes:**
- Reworked daily briefs to lead with executive summary and one-shot core
  opportunity sections: high-priority, validated digest, watchlist, local/capped,
  canonical incidents, and system health.
- Hid raw routed alertable rows behind summary text by default, filtered
  exploratory digest rows so already-promoted opportunities do not reappear as
  learning rows, and kept diagnostic card links hidden unless diagnostics are
  explicitly requested.
- Tightened near-miss detection to exclude already-promoted, alertable, zero
  score, generic/source-noise, and hard quality-context-missing rows while
  de-duplicating by incident/asset/role/impact path.
- Restricted quality-review “Possible false positives” to explicit suspicion
  reason codes instead of broad string matching, and grouped research-card
  indexes into core, near-miss, local/capped, diagnostic/control, and legacy
  sections.
- Adjusted notification inbox section labels toward core-opportunity review
  while preserving older wording for compatibility.
**Verify:** `python3 tests/test_indicators.py` passed (482/482); `make
event-alpha-signal-quality-eval PYTHON=python3` passed; `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed; `make
event-alpha-quality-validation-cycle PYTHON=python3` passed; manual smokes:
`make event-alpha-daily-brief PROFILE=catalyst_frame_e2e PYTHON=python3`,
`make event-alpha-quality-review PROFILE=catalyst_frame_e2e PYTHON=python3`,
and `make event-opportunity-audit PROFILE=catalyst_frame_e2e TARGET=VELVET
PYTHON=python3` passed; `make verify PYTHON=python3` passed.
**Notes/risks:** Presentation/reporting-only. It does not change Event Alpha
scoring, routing eligibility, Telegram send guards, paper/live trading, normal
RSI writes, or `TRIGGERED_FADE` creation.

## 2026-06-27 — Aggregate Event Alpha core opportunities · Codex
**Why:** The catalyst-frame e2e path correctly classified AAVE/Kraken/KelpDAO
and VELVET/SpaceX, but operator-facing briefs/cards/audits could still show the
same opportunity multiple ways: promoted, quality-capped support, near-miss,
exploratory, and source-noise diagnostics. The system needed one visible core
opportunity per incident/asset/role/impact family while preserving supporting
rows for audit.
**Changes:**
- Added `event_core_opportunities.py`, a pure presentation helper that
  aggregates compatible rows into core opportunities and attaches support/control
  rows as diagnostics instead of separate visible opportunities.
- Updated daily briefs, quality review, research-card indexes, and opportunity
  audit to use core opportunities by default, hide diagnostics from main lists,
  and allow explicit diagnostic review when requested.
- Added `--event-opportunity-audit-include-diagnostics` and the matching
  `INCLUDE_DIAGNOSTICS=1` Make option.
- Extended signal-quality eval output and tests with core-opportunity id,
  aggregation status, near-miss inclusion, card group, frame-counter status, and
  VELVET/AAVE/RUNE/ZEC aggregation regressions.
**Verify:** `python3 tests/test_indicators.py`; `make
event-alpha-signal-quality-eval PYTHON=python3`; `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3`; `make
event-alpha-quality-validation-cycle PYTHON=python3`; `make verify
PYTHON=python3`; manual smokes: `make
event-alpha-notify-llm-quality-frame-smoke PYTHON=python3`, `make
event-alpha-daily-brief PROFILE=catalyst_frame_e2e PYTHON=python3`, and `make
event-opportunity-audit PROFILE=catalyst_frame_e2e TARGET=AAVE PYTHON=python3`.
**Notes/risks:** Research-only presentation/reporting change. It does not change
Event Alpha scoring, route eligibility, Telegram sends, paper/live trading,
normal RSI writes, or `TRIGGERED_FADE` creation.

## 2026-06-27 — Finish Event Alpha catalyst-frame/reporting audit · Codex
**Why:** The catalyst-frame/profile audit found two remaining operator-facing
gaps: the standalone daily-brief Make target did not include test artifacts for
fixture profiles, and feedback-only calibration rows did not preserve
`incident_id`/`source_class` grouping. The existing catalyst-frame implementation
already satisfied the AAVE/Kraken/KelpDAO, VELVET aggregation, frame-counter,
frame-gating, card/audit, and doctor-wording requirements, so this pass focused
on report consistency and verification.
**Changes:**
- Updated `make event-alpha-daily-brief PROFILE=catalyst_frame_e2e` to pass the
  same test-artifact inclusion flag as the other catalyst-frame fixture report
  targets, so the generated brief selects the latest fixture run and shows
  catalyst-frame coverage instead of “No run ledger rows found.”
- Added `incident_id` to Event Alpha feedback rows and persisted it from
  watchlist entries/score components.
- Extended calibration grouping to include feedback by source class and
  incident id, including feedback-only rows without matching alert snapshots.
- Added regression coverage for the daily-brief wrapper and feedback/calibration
  grouping.
**Verify:** `python3 tests/test_indicators.py` passed (475/475); `make
event-alpha-signal-quality-eval PYTHON=python3` passed; `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed; `make
event-alpha-notify-llm-quality-frame-smoke PYTHON=python3` passed; `make
event-alpha-quality-validation-cycle PYTHON=python3` passed; `make
event-opportunity-audit PROFILE=catalyst_frame_e2e TARGET=AAVE PYTHON=python3`
passed; `make event-llm-eval PYTHON=python3`, `make event-llm-extract-eval
PYTHON=python3`, `make event-alpha-eval PYTHON=python3`, and `make verify
PYTHON=python3` passed. Also reran `make event-alpha-near-miss-report
PROFILE=notify_llm_quality PYTHON=python3`.
**Notes/risks:** Research-only artifact/report and feedback metadata changes.
No Telegram sends, paper/live trades, normal RSI rows, or provider/LLM-created
`TRIGGERED_FADE` paths were used.

## 2026-06-27 — Add frame-quality loop and sector-link guard · Codex
**Why:** The catalyst-frame layer needed a single no-send operator loop that
proves the full artifact chain, and incident relevance needed to stop treating
sector placeholder identities such as `SECTOR/sports_fan_proxy` as qualified
crypto links.
**Changes:**
- Added `make event-alpha-frame-quality-loop`, which runs signal-quality eval,
  regenerates catalyst-frame e2e artifacts, reruns quality review, incident
  report, impact-hypothesis report, daily brief, strict artifact doctor, and an
  opportunity audit target.
- Made test-artifact inclusion apply to catalyst-frame fixture profiles so
  strict doctor/report targets inspect current fixture rows.
- Broadened incident sector-placeholder detection for taxonomy identities such
  as sports fan proxy, political meme proxy, AI/RWA proxy, tokenized-stock
  venue, and prediction-market infrastructure, and exposed
  `sector_only_link_count` alongside the legacy generic counter.
- Extended regression coverage so `notify_llm_quality_frame` proves the
  AAVE/Kraken strategic-stake frame through live-style run-ledger/incident
  artifacts, THORChain/RUNE does not leak unrelated direct subjects, and broad
  sports-sector placeholder rows remain unqualified.
- Updated `ROADMAP.md`, `DECISIONS.md`, and
  `research/EVENT_ALPHA_RUNBOOK.md`.
**Verify:** `python3 tests/test_indicators.py` passed (475/475);
`python3 -m compileall -q crypto_rsi_scanner tests` passed; `make
event-alpha-signal-quality-eval PYTHON=python3` passed; `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed; `make
event-alpha-frame-quality-loop PYTHON=python3` passed; `make event-llm-eval
PYTHON=python3` passed (9/9); `make event-llm-extract-eval PYTHON=python3`
passed (7/7); `make event-alpha-eval PYTHON=python3` passed (11/11); `make
event-alpha-quality-validation-cycle PYTHON=python3` passed; `make verify
PYTHON=python3` passed.
**Notes/risks:** Research-only artifact/report hardening. The new loop sends
nothing, opens no paper/live trades, writes no normal RSI rows, and cannot
create `TRIGGERED_FADE`.

## 2026-06-27 — Polish catalyst-frame live-style reports · Codex
**Why:** The LLM catalyst-frame layer needed to be operationally consistent in
live-style quality profiles, with clear skip reasons, no stale daily-brief
selection ambiguity, and operator-facing reports that show one core opportunity
without hiding supporting evidence.
**Changes:**
- Normalized required catalyst-frame skip reasons for missing OpenAI keys,
disabled profiles, budget/deadline/no-row cases, and legacy run-ledger rows with
null frame counters.
- Added the no-send `notify_llm_quality_frame` fixture profile plus
`make event-alpha-notify-llm-quality-frame-smoke` to prove
`notify_llm_quality`-style frame artifacts, cards, incidents, hypotheses, daily
brief, quality review, and strict doctor checks without live providers or sends.
- Extended e2e/smoke Make targets so reports are generated after the cycle
instead of reading stale artifacts, and daily briefs now show the selected run
namespace.
- Preserved aggregated hypothesis supporting impact paths in watchlist/report
metadata and de-duplicated quality-review opportunity sections by core
incident/asset/role/path while keeping support counts/categories/path families
visible.
- Polished doctor/card/audit wording so healthy quality-capped rows are warnings
instead of conflicts, and cards/audits expose frame status.
- Updated `ROADMAP.md`, `DECISIONS.md`, and
`research/EVENT_ALPHA_RUNBOOK.md` with the new operating contract.
**Verify:** `python3 tests/test_indicators.py` passed (475/475);
`python3 -m compileall -q crypto_rsi_scanner tests` passed; `make
event-llm-eval PYTHON=python3` passed (9/9); `make event-llm-extract-eval
PYTHON=python3` passed (7/7); `make event-alpha-eval PYTHON=python3` passed
(11/11); `make event-alpha-signal-quality-eval PYTHON=python3` passed (32/32);
`make event-alpha-quality-validation-cycle PYTHON=python3` passed with strict
doctor warnings only; `make event-alpha-notify-llm-quality-frame-smoke
PYTHON=python3` passed with no blockers; `make
event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed with no blockers;
`make event-opportunity-audit PROFILE=catalyst_frame_e2e TARGET=AAVE
PYTHON=python3` confirmed AAVE/Kraken as the main strategic-stake frame with
KelpDAO background/negated context; `make event-alpha-daily-brief
PROFILE=catalyst_frame_e2e PYTHON=python3` wrote the brief; `make verify
PYTHON=python3` passed.
**Notes/risks:** Research-only artifact/report polish. Catalyst-frame metadata
and skip reasons still cannot create `TRIGGERED_FADE`, send notifications,
paper/live rows, normal RSI rows, or execution.

## 2026-06-27 — Operationalize catalyst-frame coverage and route caps · Codex
**Why:** The catalyst-frame layer worked in fixtures, but live-style quality
profiles needed explicit missing/unresolved frame state so ambiguous articles
cannot be silently routed as validated opportunities when the frame analyzer is
disabled, unavailable, skipped by budget, or returns unresolved output.
**Changes:**
- Added deterministic catalyst-frame requirement detection and propagated
  `catalyst_frame_required`, status, skip reason, and required-reason metadata
  onto transformed raw events and run-ledger rows.
- Capped validated impact hypotheses to exploratory/store-only research when a
  required catalyst frame is missing or unresolved, while allowing deterministic
  direct-event cases such as confirmed exploit/listing/strategic-stake paths to
  remain sufficient.
- Hardened incident linked-asset roles so taxonomy/search suggestions are
  stored as candidate suggestions instead of direct incident subjects until
  resolver/identity validation confirms the asset.
- Aggregated compatible validated hypotheses by incident, validated asset,
  role, and impact-path family, preserving supporting categories, hypothesis
  ids, and evidence quotes for audit.
- Fixed validated high-priority hypothesis routing so canonical validated
  fields can route `HIGH_PRIORITY_RESEARCH` instead of falling through to
  generic store-only block reasons.
**Verify:** `python3 tests/test_indicators.py` passed (474/474); `make
event-llm-eval PYTHON=python3` passed (9/9); `make event-llm-extract-eval
PYTHON=python3` passed (7/7); `make event-alpha-eval PYTHON=python3` passed
(11/11); `make event-alpha-signal-quality-eval PYTHON=python3` passed (32/32);
`make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed with no
blockers; `make event-alpha-quality-validation-cycle PYTHON=python3` passed;
`python3 -m compileall -q crypto_rsi_scanner tests` passed; manual smoke
reports for `event-opportunity-audit TARGET=AAVE`, `event-incidents-report`,
and `event-alpha-daily-brief` under `PROFILE=catalyst_frame_e2e` passed; `make
verify PYTHON=python3` passed.
**Notes/risks:** Research-only artifact and routing-quality hardening. Missing
or unresolved LLM frames can cap ambiguous research routes, but they still
cannot create `TRIGGERED_FADE`, send notifications, open paper/live rows, write
normal RSI signals, bypass resolver/quality/event-fade gates, or execute trades.


## 2026-06-27 — Prove catalyst-frame semantics through Event Alpha artifacts · Codex
**Why:** The LLM catalyst-frame eval proved AAVE/Kraken/KelpDAO in isolation, but the operational artifacts could still be generated from pre-LLM raw rows. The proof needed to run through the full Event Alpha pipeline so cards, audits, incidents, hypotheses, watchlist state, daily brief, and run ledger all agree.
**Changes:**
- Changed the Event Alpha raw-event transform path so downstream hypothesis/incident generation receives the transformed rows after source enrichment, extraction hints, and validated LLM catalyst frames.
- Promoted catalyst-frame metadata through canonical incidents, incident-store rows, impact hypotheses, score components, cards, opportunity audits, daily briefs, and run-ledger counters. Rows now preserve main frame role/subject/actor/object/evidence, corrective frame ids, selected-main reason, rule/LLM predictions, disagreement resolution, and rejected background/corrective impact paths.
- Added the isolated `catalyst_frame_e2e` fixture profile, AAVE/THORChain/MemeCore/ZEC/VELVET e2e fixtures, and `make event-alpha-catalyst-frame-e2e-cycle`, writing artifacts under `event_fade_cache/catalyst_frame_e2e/` without live providers or sends.
- Added regression tests proving AAVE stays `strategic_investment_or_valuation`, KelpDAO exploit language is rejected background/corrective context, THORChain remains direct exploit, MemeCore remains unknown market dislocation, and no fixture creates `TRIGGERED_FADE`.
**Verify:** `python3 tests/test_indicators.py` passed (470/470); `make event-alpha-signal-quality-eval PYTHON=python3` passed (32/32); `make event-alpha-quality-validation-cycle PYTHON=python3` passed; `make event-alpha-catalyst-frame-e2e-cycle PYTHON=python3` passed; manual `make event-opportunity-audit PROFILE=catalyst_frame_e2e TARGET=AAVE PYTHON=python3` showed AAVE/Kraken as `acquisition_or_stake` with KelpDAO background/corrective rejected; `make verify PYTHON=python3` passed.
**Notes/risks:** Research-only artifact hardening. Validated LLM frames still cannot send notifications, create paper/live rows, write normal RSI signals, bypass quality/resolver/event-fade gates, or create `TRIGGERED_FADE`.

## 2026-06-27 — Add quote-validated LLM catalyst-frame analyzer · Codex
**Why:** Deterministic catalyst framing now separates main/background context,
but AAVE/Kraken/KelpDAO-style articles need a constrained semantic support
layer so the source's main catalyst can be recognized without letting an LLM
invent identity, impact paths, routes, or triggers.
**Changes:**
- Added `event_llm_catalyst_frames.py` and
  `event_catalyst_frame_validator.py` with strict structured frame models,
  quote validation, external-entity/crypto-identity guards, generic ticker-word
  collision rejection, rejected impact paths, manual verification items, and
  explicit rule-vs-LLM disagreement resolution.
- Added fixture and OpenAI provider support for catalyst-frame analysis, plus
  fixture golden cases for AAVE/Kraken/KelpDAO, THORChain/RUNE, MemeCore,
  ZEC/miner listing, VELVET/SpaceX, and invalid-quote rejection.
- Wired validated LLM frames into the unified Event Alpha raw-event transform so
  deterministic incident/impact logic can consume only validated frames; raw
  LLM output is ignored unless the validator accepts it.
- Added catalyst-frame counters to the Event Alpha pipeline report/run ledger,
  `RSI_EVENT_LLM_CATALYST_FRAMES_*` config, profile rollout (`notify_no_key`
  off, OpenAI LLM profiles bounded/on, fixture `catalyst_frame_validation`),
  `make event-alpha-catalyst-frame-validation-cycle`, signal-quality fixtures,
  tests, and docs.
**Verify:** `python3 tests/test_indicators.py` passed (469/469);
`python3 -m compileall -q crypto_rsi_scanner tests` passed; `make
event-llm-eval PYTHON=python3` passed (9/9); `make event-llm-extract-eval
PYTHON=python3` passed (7/7); `make event-alpha-eval PYTHON=python3` passed
(11/11); `make event-alpha-signal-quality-eval PYTHON=python3` passed (32/32);
`make event-alpha-catalyst-frame-validation-cycle PYTHON=python3` passed,
including AAVE/Kraken resolving to `acquisition_or_stake` with `llm_wins`;
`make event-alpha-quality-validation-cycle PYTHON=python3` passed with strict
doctor WARN only for weak unqualified fixture links; `make verify PYTHON=python3`
passed. Manual `make event-opportunity-audit PROFILE=catalyst_frame_validation
TARGET=AAVE PYTHON=python3` ran safely but found no artifact row because AAVE is
currently an eval fixture, not part of that profile's anomaly source cycle;
`make event-alpha-daily-brief PROFILE=catalyst_frame_validation PYTHON=python3`
wrote the fixture daily brief.
**Notes/risks:** Research-only semantic metadata. Validated LLM frames can inform
incident/impact artifacts, but cannot create `TRIGGERED_FADE`, send Telegram,
open paper/live trades, write normal RSI rows, bypass resolver/quality gates, or
alter event-fade eligibility.

## 2026-06-27 — Add Event Alpha main-catalyst frames · Codex
**Why:** Event Alpha could misread an article's background context as the
actionable catalyst. The concrete failure was an AAVE/Kraken strategic-stake
article being treated as an `exploit_security_event` because the body mentioned
KelpDAO exploit history and corrective “Aave itself not hacked” language.
**Changes:**
- Added `event_catalyst_frames.py`, a pure deterministic catalyst-frame layer
  that separates main catalysts from background, historical, negated,
  corrective, side-note, policy, proxy, and market-reaction context.
- Wired frame selection into incident graph/store, impact-path validation,
  impact-hypothesis generation, opportunity verdict quality, daily briefs,
  research cards, and opportunity audits; rows now preserve main/background/
  negated frame metadata and rejected/background impact paths.
- Added a strategic-investment/valuation impact path and reason so AAVE/Kraken
  style stake/valuation events validate as direct strategic catalysts rather
  than exploit/security events.
- Hardened broad prediction-market/source-context handling so hidden diagnostic
  rows keep useful subjects without becoming canonical crypto incidents.
**Verify:** `python3 tests/test_indicators.py` passed (465/465); `make
event-llm-eval PYTHON=python3` passed (9/9); `make event-llm-extract-eval
PYTHON=python3` passed (7/7); `make event-alpha-eval PYTHON=python3` passed
(11/11); `make event-alpha-signal-quality-eval PYTHON=python3` passed (31/31);
`make event-alpha-quality-validation-cycle PYTHON=python3` completed with
strict doctor WARN only for weak unqualified links and no blockers; `make
verify PYTHON=python3` passed.
**Notes/risks:** Research-only classification/artifact-truth change. No sends,
paper rows, normal RSI rows, trading, execution, or LLM/provider-created
`TRIGGERED_FADE`; deterministic `event_fade.py` + `proxy_fade` remains the only
fade trigger path.

## 2026-06-26 — Enforce Event Alpha live-path quality caps and incident subjects · Codex
**Why:** Fresh `notify_llm_quality` artifacts still had non-hypothesis
CHZ/SOL/ADA/DOGE-style rows persisted as `WATCHLIST` despite local-only,
zero-score, insufficient-data quality verdicts. Incident artifacts also
contained boilerplate/SEO subjects such as `About`, `All`, `LLM`, and
`Polymarket Invite Code SBWIRE` as canonical-looking rows.
**Changes:**
- Added a watchlist persistence safety cap so hand-built or non-hypothesis
  entries are normalized through `quality_cap_watchlist_state` before JSONL
  write; active states with local-only/insufficient-data/unknown-role quality
  now persist as `QUALITY_BLOCKED` with requested/final state fields.
- Updated artifact doctor to inspect path-scoped watchlist rows even when older
  rows lack embedded profile/namespace metadata, so non-hypothesis quality
  conflicts are no longer invisible.
- Added a central incident primary-subject validator and wired it into
  incident graph/store paths before persistence; garbage subjects are
  diagnostic-only/rejected or replaced by validated context instead of stored
  as valid canonical incidents.
- Added regressions for the exact CHZ-style non-hypothesis watchlist shape and
  the garbage incident subject list.
**Verify:** `python3 tests/test_indicators.py` passed (463/463); `make
event-llm-eval PYTHON=python3` passed (9/9); `make event-llm-extract-eval
PYTHON=python3` passed (7/7); `make event-alpha-eval PYTHON=python3` passed
(11/11); `make event-alpha-signal-quality-eval PYTHON=python3` passed (31/31);
`make event-alpha-quality-validation-cycle PYTHON=python3` completed with
strict doctor WARN only for weak unqualified links and no blockers; `make
event-alpha-quality-live-smoke PROFILE=notify_llm_quality PYTHON=python3`
completed with fail-soft provider warnings and strict doctor WARN/no blockers;
manual artifact checks found 0 active bad watchlist rows and 0 bad canonical
incident subjects; `make verify PYTHON=python3` passed.
**Notes/risks:** Research-only artifact truth/hygiene change. No sends, paper
rows, normal RSI rows, trading, execution, or LLM/provider-created
`TRIGGERED_FADE`; deterministic `event_fade.py` + `proxy_fade` remains the only
fade trigger path.

## 2026-06-26 — Use final opportunity verdicts and refresh near-misses · Codex
**Why:** `notify_llm_quality` artifacts showed candidates with
`opportunity_score_final=72` and `opportunity_level=validated_digest` still
kept local because the router consulted stale `opportunity_score_v2=64`. Near
misses blocked mostly by missing market evidence also needed bounded targeted
refresh before final routing.
**Changes:**
- Made Event Alpha routing use canonical `opportunity_score_final` and
  `opportunity_level` for validated-hypothesis digest decisions; older
  `opportunity_score_v2` and `hypothesis_score` remain audit fields only.
- Added `event_near_miss.py` to identify near-promotion candidates, reject
  generic/source-noise rows, run bounded market/enrichment refreshes when
  enabled, recompute final opportunity verdicts, and store before/after
  diagnostics without creating alerts or triggers.
- Wired near-miss refresh into the Event Alpha pipeline and `notify_llm`/
  `notify_llm_deep`/`notify_llm_quality` profiles, plus
  `--event-alpha-near-miss-report` and `make event-alpha-near-miss-report`.
- Added near-miss sections to daily briefs and opportunity audits, and exposed
  route-report fields `routing_score_used`, `routing_score_source`, and
  `routing_verdict_used`.
**Verify:** Focused router/near-miss tests passed; `python3
tests/test_indicators.py` passed (461/461); `make
event-alpha-signal-quality-eval PYTHON=python3` passed (31/31); `make
event-alpha-quality-validation-cycle PYTHON=python3` completed with strict
doctor `WARN` only for weak unqualified incident links and no blockers; `make
verify PYTHON=python3` passed. Manual smokes: `make
event-alpha-quality-review PROFILE=notify_llm_quality PYTHON=python3`,
`make event-alpha-near-miss-report PROFILE=notify_llm_quality PYTHON=python3`,
and `make event-opportunity-audit PROFILE=notify_llm_quality TARGET=AAVE
PYTHON=python3` all completed.
**Notes/risks:** Research-only artifact/route quality control. This does not
send notifications by itself, create paper/live trades, write normal RSI rows,
or create `TRIGGERED_FADE`; deterministic `event_fade.py` plus `proxy_fade`
remains the only fade trigger source.

## 2026-06-26 — Require quality-qualified incident links · Codex
**Why:** Broad external events such as Annexation, Macron, OpenAI, Metamask,
and Databricks were still appearing as `active_incident` because stale/legacy
watchlist links existed, even when those links were unknown-role, sector-only,
or quality-blocked. Active incident status needs to mean a real
quality-qualified crypto link exists.
**Changes:**
- Added incident link-quality classification with raw, qualified, weak,
  quality-blocked, unknown-role, and sector-only link counts plus reason codes.
- Changed incident relevance so `active_incident` requires a qualified
  hypothesis/watchlist link or explicit non-blocked material update; weak links
  now leave rows as `incident_candidate` or hidden `external_context_only`.
- Hardened legacy artifact reads so old no-status or legacy-linked rows are
  downgraded at report time when their links are not quality-qualified.
- Surfaced link quality in incident reports, daily briefs, opportunity audits,
  artifact doctor checks, signal-quality evals, and regression tests.
**Verify:** Focused incident relevance tests passed; `python3
tests/test_indicators.py` passed (460/460); `make
event-alpha-signal-quality-eval PYTHON=python3` passed (31/31); `make
event-alpha-quality-validation-cycle PYTHON=python3` completed with strict
doctor warnings only for weak unqualified links and no blockers; `make verify
PYTHON=python3` passed. Manual `notify_llm_quality` smoke: incidents report now
shows `active_incidents: 0`, `linked_incidents: 0`, and weak OpenAI/Databricks/
Anthropic rows as `incident_candidate`; strict doctor has no incident-link
blockers; daily brief writes with incident candidates separated from active
qualified incidents.
**Notes/risks:** Research-only artifact classification. No normal RSI rows,
paper/live trades, execution, Telegram promotion, or LLM/provider-created
`TRIGGERED_FADE` behavior changed.

## 2026-06-26 — Split external context from raw incident relevance · Codex
**Why:** The first incident relevance gate hid broad unlinked events, but it
still collapsed generic external context and raw observations into the same
bucket. Pro review asked for a clearer `external_context_only` status plus a
separate opt-in for storing raw/external rows.
**Changes:**
- Added `external_context_only` incident relevance status for broad political,
  sports, prediction-market, and geopolitical context that has no validated
  crypto asset, hypothesis, watchlist row, or market-dislocation link.
- Added `RSI_EVENT_INCIDENT_STORE_RAW_OBSERVATIONS`; diagnostic/rejected rows
  still use `RSI_EVENT_INCIDENT_STORE_DIAGNOSTIC`, while raw/external-context
  rows can be stored separately for audits.
- Extended incident reports, daily briefs, artifact doctor, and signal-quality
  evals with separate diagnostic/raw/external-context hidden counts and flags.
- Updated regression coverage so Polymarket/Annexation-style context is
  `external_context_only`, truly unstructured rows are `raw_observation`, and
  linked/crypto-relevant incidents still persist normally.
**Verify:** `python3 tests/test_indicators.py` passed (460/460);
`make event-llm-eval PYTHON=python3` passed (9/9); `make
event-llm-extract-eval PYTHON=python3` passed (7/7); `make
event-alpha-eval PYTHON=python3` passed (11/11); `make
event-alpha-signal-quality-eval PYTHON=python3` passed (31/31); `make
event-alpha-quality-validation-cycle PYTHON=python3` completed with strict
doctor `OK`; `make verify PYTHON=python3` passed. Manual `notify_llm_quality`
smoke: `make event-incidents-report` now shows `canonical_unlinked_incidents:
0`; strict artifact doctor reports no blockers and only hidden diagnostic/raw/
external-context warnings; daily brief writes successfully.
**Notes/risks:** Research-only artifact classification. No normal RSI rows,
paper/live trades, execution, Telegram promotion, or LLM/provider-created
`TRIGGERED_FADE` behavior changed.

## 2026-06-26 — Gate canonical incidents by crypto relevance · Codex
**Why:** Event Alpha was preserving broad external events as canonical incidents
even when they had no validated crypto asset, hypothesis, watchlist linkage, or
market reaction. That made incident reports look more actionable than the
underlying evidence justified.
**Changes:**
- Added explicit incident relevance statuses:
  `raw_observation`, `incident_candidate`, `canonical_incident`,
  `linked_incident`, `active_incident`, `diagnostic_only`, and
  `rejected_incident`.
- Added relevance scoring, reason codes, warnings, and
  `canonical_persistence_reason` fields to incident rows, impact hypotheses,
  hypothesis-store rows, watchlist metadata, alert snapshots, daily briefs,
  opportunity audits, research cards, and artifact doctor output.
- Changed incident-store writes so live-style profiles persist canonical,
  linked, active, and candidate incidents by default, while raw/diagnostic/
  rejected observations are hidden unless `RSI_EVENT_INCIDENT_STORE_DIAGNOSTIC=1`
  or a fixture/debug profile is running.
- Updated signal-quality fixtures and regression tests for raw Polymarket/
  geopolitical observations, linked OpenAI sector incidents, RWA/pre-IPO
  candidates, market anomalies, and active THORChain/RUNE-style incidents.
**Verify:** `python3 tests/test_indicators.py` passed (460/460);
`make event-alpha-signal-quality-eval PYTHON=python3` passed (31/31);
`make event-alpha-quality-validation-cycle PYTHON=python3` completed with
strict doctor `OK`; `make verify PYTHON=python3` passed. Fresh
`make event-alpha-quality-live-smoke PROFILE=notify_llm_quality_fresh
PYTHON=python3` completed with 200 raw events, 198/200 extraction rows, 49
extraction hints, 104 hypotheses, 91 persisted incidents, 0 alertable routes,
0 sends, 0 missing relevance fields, 0 raw/rejected diagnostic rows persisted by
default, and strict doctor `WARN` only for 8 canonical unlinked incident review
warnings. Manual `make event-incidents-report`, `make
event-alpha-artifact-doctor STRICT=1`, and `make event-alpha-daily-brief` passed
for `notify_llm_quality_fresh`.
**Notes/risks:** Research-only artifact relevance gating. This does not create
events, watchlist states, notifications, paper/live trades, normal RSI rows, or
LLM/provider-created `TRIGGERED_FADE`; deterministic `event_fade.py` remains the
only fade trigger source.

## 2026-06-26 — Add fresh live-style quality proof target · Codex
**Why:** The checked-in/local `notify_llm_quality` artifact namespace can contain
older pre-fix rows, so Pro-model review needed a clean live-style proof run that
does not rely on stale watchlist or incident artifacts.
**Changes:**
- Added a `notify_llm_quality_fresh` profile that mirrors `notify_llm_quality`
  inputs and quality gates while writing to an isolated notification-burn-in
  artifact namespace.
- Added `make event-alpha-notify-llm-quality-fresh-cycle` and
  `make event-alpha-quality-live-smoke PROFILE=notify_llm_quality_fresh`; the
  target clears only the fresh namespace, runs the no-send quality cycle with
  wall-clock time, then prints the daily brief, quality review, incident report,
  and strict artifact doctor output.
- Added regression coverage that the fresh profile is no-send,
  notification-burn-in, impact-path gated, and that the Make dry-run contains no
  `--event-alert-send`, fixture clock, or fixed research clock.
- Updated the runbook/roadmap/decisions to treat `quality_validation` as fixture
  proof and `notify_llm_quality_fresh` as the clean live-style proof path when
  stale artifacts are suspected.
**Verify:** Baseline `python3 tests/test_indicators.py` passed (459/459);
`make event-alpha-signal-quality-eval PYTHON=python3`; `make verify
PYTHON=python3`. Fresh `make event-alpha-quality-live-smoke
PROFILE=notify_llm_quality_fresh PYTHON=python3` completed with
`send_requested=false`, 186 watchlist rows, 18 quality-capped rows, 0 bad active
watchlist rows, 155 incident rows, 0 garbage canonical incidents, and strict
artifact doctor exit 0 with warnings only for unlinked valid incident rows. Final
verification also ran `make event-alpha-quality-validation-cycle PYTHON=python3`
and `make verify PYTHON=python3`.
**Notes/risks:** Research-only proof tooling. No Telegram send was requested; no
normal RSI rows, paper/live trades, execution, or LLM/provider-created
`TRIGGERED_FADE` behavior changed.

## 2026-06-26 — Harden quality lifecycle caps and incident subjects · Codex
**Why:** Fresh `notify_llm_quality` artifacts could still show non-hypothesis
rows as active `WATCHLIST` even when their quality verdict said
`local_only`/insufficient data, and canonical incidents could use prose
fragments such as `Actions`, `However`, `LLM`, or SEO/referral phrases as
primary subjects.
**Changes:**
- Extended watchlist lifecycle caps to block active states when quality fields
  show `candidate_role=unknown_with_reason`, `source_class=insufficient_data`,
  `evidence_specificity=insufficient_data`, zero final score, or insufficient
  impact path.
- Applied conservative quality defaults and final-state recomputation to
  non-hypothesis alert/playbook/market-anomaly rows, so stale persisted
  `final_state_after_quality_gate=WATCHLIST` cannot override a local-only
  verdict.
- Hardened artifact doctor counters for universal, hypothesis, non-hypothesis,
  safely capped, uncapped, legacy, diagnostic, and invalid incident conflicts.
- Tightened claim/incident subject validation so generic prose fragments are
  rejected; invalid canonical incidents are stored as diagnostic-only unless
  linked to real hypothesis/watchlist context, and hidden from default incident
  reports. Existing persisted garbage subjects are also quarantined at read
  time unless `--include-diagnostic-incidents` is requested.
- Expanded regression coverage for capped non-hypothesis rows, fresh uncapped
  watchlist conflicts, diagnostic incident rows, and subject cleanup such as
  `OpenAI This` -> `OpenAI`, `Polymarket World Cup Volume` -> `World Cup`, and
  stale `LLM` rows becoming diagnostic-only.
**Verify:** `python3 tests/test_indicators.py` passed (459/459);
`make event-alpha-signal-quality-eval PYTHON=python3`;
`make event-alpha-quality-validation-cycle PYTHON=python3`;
`make verify PYTHON=python3`. Manual `notify_llm_quality` quality review,
daily brief, strict artifact doctor, inbox, and incident report smoke commands
completed; strict doctor had no blockers, and the default incident report hid
the stale `LLM` diagnostic row.
**Notes/risks:** Research-only artifact hygiene. No normal RSI rows, paper/live
trades, execution, Telegram-send promotion, or LLM/provider-created
`TRIGGERED_FADE` behavior changed.

## 2026-06-26 — Finish incident-spine quality artifacts · Codex
**Why:** `notify_llm_quality` needed a no-send validation path that writes the
same canonical incident artifacts as the clean fixture namespace, and strict
doctor checks needed to distinguish intentional no-incident evidence from fresh
rows that silently lost their incident linkage.
**Changes:**
- Added explicit `incident_link_status` / `incident_link_reason` propagation
  through impact hypotheses, hypothesis-store rows, hypothesis watchlist rows,
  and alert snapshots.
- Hardened artifact doctor so `no_incident` only bypasses missing-incident
  checks when an explicit reason is present, while still preserving legacy
  warning behavior.
- Tightened market-anomaly incident roles so validated anomaly assets from the
  market payload become `direct_subject`, sector context cannot masquerade as
  the direct subject, and missing validated anomaly identity is warned.
- Added `make event-alpha-notify-llm-quality-validation-cycle`, a fresh
  `notify_llm_quality` no-send rebuild that writes the daily brief, incident
  report, quality review, and strict artifact-doctor output.
- Expanded incident regression coverage for SOL/USDT anomaly roles,
  missing-anomaly-asset warnings, intentional no-incident rows, and the new
  no-send quality target.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed;
`python3 tests/test_indicators.py` passed (459/459). Broader Make verification
is run before commit.
**Notes/risks:** Research-only artifact and operator-target hardening. No
normal RSI rows, paper/live trades, execution, Telegram send promotion, or
LLM/provider-created `TRIGGERED_FADE` behavior changed.

## 2026-06-26 — Make canonical incidents the Event Alpha spine · Codex
**Why:** The incident store existed, but incident identity still needed to be
the durable join key across hypotheses, watchlist rows, alert snapshots, run
ledgers, reports, and artifact health checks. Otherwise duplicate source
updates could still fragment state or hide missing incident linkage.
**Changes:**
- Propagated `incident_*` aliases and `hypothesis_id` through impact
  hypotheses, hypothesis JSONL rows, watchlist rows, route alert snapshots, and
  incident reports.
- Changed hypothesis watchlist keys to use
  `incident_id + asset/sector identity + candidate_role + impact_path_type`
  when an incident id exists, while warning on hypothesis rows that lack an
  incident id.
- Added incident-specific material update reasons for new independent sources,
  cause-status changes, confirmed/ruled-out/conflicting claims, market reaction
  confirmation, causal-mechanism confirmation, and affected-role changes.
- Extended run-ledger and incident reports with linked-hypothesis/watchlist
  counts, and artifact doctor strict checks for missing incident ids or
  incident rows that do not link back to hypotheses/watchlist state.
- Made `make event-alpha-artifact-doctor PROFILE=quality_validation STRICT=1`
  include test artifacts automatically so the documented validation smoke
  inspects the fresh fixture namespace instead of filtering it out.
- Expanded incident regression coverage for SecondFi duplicate-source updates,
  THORChain/RUNE alert snapshots, incident-linked doctor checks, and missing
  incident-id blockers.
**Verify:** `python3 tests/test_indicators.py` passed (459/459);
`make event-alpha-signal-quality-eval PYTHON=python3` passed (26/26);
`make event-alpha-quality-validation-cycle PYTHON=python3` passed with strict
artifact doctor `OK`; `make event-incidents-report PROFILE=quality_validation
PYTHON=python3` and `make event-opportunity-audit PROFILE=quality_validation
TARGET=SOL PYTHON=python3` printed fresh incident/audit context; `make
event-alpha-artifact-doctor PROFILE=quality_validation STRICT=1 PYTHON=python3`
returned `OK`; `make verify PYTHON=python3` passed.
**Notes/risks:** Research-only artifact identity and reporting hardening. No
normal RSI rows, paper/live trades, execution, alert promotion, or
LLM/provider-created `TRIGGERED_FADE` behavior changed.

## 2026-06-26 — Fix no-catalyst incident semantics · Codex
**Why:** Fresh `quality_validation` artifacts showed a bad canonical incident
named `No · market anomaly`, with `primary_subject=No` and a misleading
`No explains_market_move` claim. “No dated external catalyst has been
validated” is absence-of-evidence, not a confirmed causal claim, and unrelated
market anomalies must not merge under a generic unknown-cause incident.
**Changes:**
- Tightened claim semantics so no-catalyst/no-clear-trigger phrases become
  `absence_of_validated_catalyst` / unknown-cause metadata instead of confirmed
  `explains_market_move` claims.
- Added subject guardrails for generic terms such as `No`, `Unknown`,
  `Market`, `Catalyst`, `Token`, and `Coin`, with market anomalies falling back
  to the asset symbol/coin id from the raw anomaly payload.
- Made market-anomaly incident identity asset/date/anomaly-specific, so SOL and
  USDT anomalies on the same date are separate incidents while repeated SOL
  anomaly rows can merge.
- Added `market_reaction_observed` to incident rows/reports so observed market
  movement remains distinct from confirmed causal mechanism, and updated
  incident reports/daily briefs/audits accordingly.
- Expanded tests and signal-quality fixtures for no-catalyst phrases, no-exploit
  language, SOL/Tether market anomalies, MemeCore no-exploit dislocation,
  THORChain confirmed exploit, and SecondFi duplicate-source merging.
**Verify:** `python3 tests/test_indicators.py` passed (459/459);
`make event-alpha-signal-quality-eval PYTHON=python3` passed (26/26);
`make event-alpha-quality-validation-cycle PYTHON=python3` passed with strict
artifact doctor `OK`; `make event-incidents-report PROFILE=quality_validation
PYTHON=python3` showed separate `SOL market anomaly` and `USDT market anomaly`
rows with `cause=unknown`, `reaction_observed=true`, and `causal=false`.
Full `make verify` is run before commit.
**Notes/risks:** Research-only semantic/artifact hardening. No normal RSI rows,
paper/live trades, execution, alert promotion, or LLM/provider-created
`TRIGGERED_FADE` behavior changed.

## 2026-06-26 — Persist canonical Event Alpha incidents · Codex
**Why:** Claim semantics and incident clustering were available in-memory, but
operators and Pro-model reviews needed durable incident artifacts that link raw
sources, claims, hypotheses, watchlist rows, cards, audits, and opportunity
verdicts.
**Changes:**
- Added a profile-scoped `event_incidents.jsonl` artifact store and
  `--event-incidents-report` / `make event-incidents-report`, plus run-ledger,
  pipeline, profile-context, and config path wiring.
- Linked incident ids/confidence/cause/claim/market context through impact
  hypotheses, watchlist material-change reasons, alert snapshots, daily briefs,
  opportunity audits, and research cards.
- Tightened opportunity verdict handling so ruled-out exploit causes hard-block
  exploit paths and suspected ecosystem/direct incidents remain capped until
  cause and market reaction are confirmed.
- Expanded tests for SecondFi duplicate-source incident merging, MemeCore
  market reaction without causal confirmation, THORChain/RUNE direct incidents,
  incident report/brief/card/audit context, and incident-aware verdict caps.
**Verify:** Focused incident regressions and `python3 -m compileall -q
crypto_rsi_scanner tests` passed. Full verification is run before commit.
**Notes/risks:** Research-only artifact/reporting and verdict-safety hardening.
No normal RSI rows, paper/live trades, execution, notification promotion, or
LLM/provider-created `TRIGGERED_FADE` behavior changed.

## 2026-06-26 — Add Event Alpha claim semantics and incident intelligence · Codex
**Why:** Event Alpha could validate broad co-occurrence too aggressively when a
source implied an exploit, policy risk, or ecosystem incident without preserving
claim polarity, cause status, canonical incident identity, or the candidate's
actual role in the event. The radar needs to distinguish confirmed impact paths
from negated/unknown causes and third-party ecosystem exposure before routing
research artifacts.
**Changes:**
- Added pure claim-semantics extraction for asserted, alleged, negated,
  disputed, denied, ruled-out, and unknown-cause event claims, plus cause-status
  helpers used by impact validation and signal-quality evals.
- Added canonical incident clustering and affected-asset role classification so
  duplicate articles merge by incident subject/archetype/ecosystem/date and
  candidates can be labeled as direct subjects, ecosystem-affected assets,
  proxy instruments/venues, infrastructure providers, macro-affected assets, or
  generic mentions.
- Updated impact-path validation and impact hypotheses to propagate incident
  ids, primary subjects, affected ecosystems, candidate role confidence,
  claim history, source domains, market-context source/age/data-quality, market
  reaction confirmation, and causal-mechanism confirmation into watchlist rows,
  quality review, daily briefs, and research cards.
- Versioned source-enrichment cache rows with a cleaner version and text/content
  hashes so stale cleaned-source artifacts are refetched/recleaned instead of
  silently reused.
- Expanded signal-quality fixtures and unit coverage for ruled-out exploit
  market dislocations, third-party ecosystem exploits, alleged/unconfirmed
  exploits, incident dedupe, and market-context propagation.
**Verify:** `python3 tests/test_indicators.py` passed (457/457). Plain
`python3` lacks `aiohttp` for dependency-heavy Make targets on this machine, so
the project venv was used for full verification:
`make event-llm-eval PYTHON=.venv/bin/python`,
`make event-llm-extract-eval PYTHON=.venv/bin/python`,
`make event-alpha-eval PYTHON=.venv/bin/python`,
`make event-alpha-signal-quality-eval PYTHON=.venv/bin/python`,
`make event-alpha-quality-validation-cycle PYTHON=.venv/bin/python`, and
`make verify PYTHON=.venv/bin/python` all passed.
**Notes/risks:** Research-only metadata and artifact quality hardening. No
normal RSI rows, paper/live trades, execution, route promotion, provider/LLM
promotion, or LLM/provider-created `TRIGGERED_FADE` behavior changed.

## 2026-06-25 — Clean Event Alpha state-cap reasons and candidate funnel counts · Codex
**Why:** The lifecycle cap was in place, but some legacy/local-only rows could
still display positive-sounding block reasons such as `strong_market_confirmation`,
and candidate-discovery reports could make raw/taxonomy terms look like
candidate-like assets.
**Changes:**
- Normalized quality/state gate block reasons so positive evidence stays in
  score components and blockers say what is missing (`needs_strong_market_confirmation`,
  `weak_impact_path_despite_market_confirmation`, `missing_direct_impact_path`,
  or `impact_path_not_strong_enough`).
- Updated opportunity verdict generation so new local/exploratory verdicts no
  longer use `strong_market_confirmation` as a missing requirement.
- Tightened candidate-discovery funnel reporting so taxonomy/source/navigation
  terms are counted as raw terms but not `candidate_like_terms` unless they are
  actually accepted/validated; legacy raw-term counters are explicitly labeled.
- Added regression coverage for reason normalization, market confirmation as
  positive evidence, and raw/taxonomy/generic-HYPE funnel accounting.
**Verify:** `python3 tests/test_indicators.py` passed (456/456);
`make event-llm-eval PYTHON=python3`, `make event-llm-extract-eval PYTHON=python3`,
`make event-alpha-eval PYTHON=python3`, `make event-alpha-signal-quality-eval PYTHON=python3`,
and `make event-alpha-quality-validation-cycle PYTHON=python3` passed before
this log entry. Full `make verify PYTHON=python3` is run at handoff.
**Notes/risks:** Research-only reporting/metadata cleanup. No normal RSI rows,
paper/live trades, execution, route promotion, or `TRIGGERED_FADE` creation
changed.

## 2026-06-25 — Make Event Alpha quality verdicts authoritative over lifecycle state · Codex
**Why:** The daily brief could still show a stale BTC/World Cup/Bitcoin World
row as active `WATCHLIST` even after the final quality verdict downgraded it to
`local_only`, `opportunity_score_final=0`, `impact_path_type=insufficient_data`,
and final route `STORE_ONLY`. Quality gates need to cap watchlist lifecycle
state, not only notification routing.
**Changes:**
- Added quality-capped lifecycle state handling in `event_watchlist.py`,
  including `QUALITY_BLOCKED`, `quality_cap_watchlist_state`, and persisted
  requested/final state fields plus block reasons on watchlist rows and alert
  snapshots.
- Updated router, active monitor, daily brief, research cards, quality review,
  notification inbox, and artifact doctor consumers to use final
  quality-capped state for active watchlist/routing decisions while preserving
  requested state for audit.
- Daily brief and quality review now separate `Quality-Capped Watchlist Rows`
  from active watchlist rows; research cards explain why a requested
  `WATCHLIST` was blocked and what would upgrade it.
- Artifact doctor now reports watchlist state conflicts with quality and blocks
  fresh uncapped conflicts in strict mode while treating legacy conflicts as
  warnings unless strict-legacy review is requested.
**Verify:** `python3 tests/test_indicators.py` passed (456/456);
`make event-llm-eval PYTHON=python3`, `make event-llm-extract-eval PYTHON=python3`,
`make event-alpha-eval PYTHON=python3`, `make event-alpha-signal-quality-eval PYTHON=python3`,
`make event-alpha-quality-validation-cycle PYTHON=python3`, and
`make verify PYTHON=python3` all passed. Manual smokes for
`notify_llm_quality` quality review, daily brief, strict artifact doctor, and
notification inbox passed.
**Notes/risks:** Research-only. No normal RSI rows, paper/live trades,
execution, alert-scoring promotion, provider/LLM promotion, or
LLM/provider-created `TRIGGERED_FADE` behavior changed. Deterministic
`event_fade.py` + `proxy_fade` remains the only `TRIGGERED_FADE` source.

## 2026-06-25 — Canonicalize Event Alpha quality artifact truth · Codex
**Why:** Fresh alert snapshots can be quality-gated correctly while older
pre-quality fields still make raw rows look alertable to downstream reports.
Operator review, Pro-model handoff, and policy simulation need one canonical
post-quality route/tier contract.
**Changes:**
- Alert snapshots now always carry requested route/tier, final
  route/tier-after-quality-gate, alertable-after-quality-gate, block reason,
  and a snapshot-quality classification (`current_clean`,
  `quality_gated_local`, `legacy_conflict`, `missing_final_route`, or
  `stale_pre_quality_gate`).
- Snapshot reports, notification inbox, daily brief, research cards, artifact
  doctor, quality review, and policy simulation now use the final route by
  default while preserving requested/legacy route fields for audit.
- Legacy quality-route conflicts are quarantined from delivered/would-send
  feedback queues by default; fresh conflicts and fresh missing final routes
  block strict artifact doctor checks, with an explicit strict-legacy option
  for migration audits.
- Candidate-discovery funnel reporting now separates raw terms, candidate-like
  terms, resolver attempts/accepted/rejected terms, context-validated
  candidates, and promoted candidates; quality review adds deterministic tuning
  suggestions for near-threshold rows, weak co-occurrence patterns, source
  blockers, and next experiments.
**Verify:** `python3 tests/test_indicators.py` passed (456/456) and
`python3 -m compileall -q crypto_rsi_scanner tests` passed. Full eval,
quality-validation, manual smoke, and `make verify` results are in the final
handoff for this prompt.
**Notes/risks:** Research-only. No normal RSI rows, paper/live trades,
execution, alert-scoring promotion, provider/LLM promotion, or
LLM/provider-created `TRIGGERED_FADE` behavior changed.

## 2026-06-25 — Make Event Alpha quality verdicts final at snapshot and notification boundaries · Codex
**Why:** A row with a final `local_only` / `insufficient_data` verdict could be
downgraded in the daily brief while stale pre-gate route fields still made it
look like a would-send research digest in alert snapshots and the notification
inbox. The final quality route has to be authoritative at every operator-facing
boundary, not just in the router report.
**Changes:**
- Added shared final-route helpers so Event Alpha route decisions, notification
  plans, routed Telegram copy, and alertable-decision lists read
  `final_route_after_quality_gate` instead of trusting pre-gate route state.
- Alert snapshots now persist final `route`, `lane`, `tier`, `route_alertable`,
  and `alertable_after_quality_gate`; the original requested route/tier remain
  for audit. Quality-gated local/store-only rows no longer count as alertable
  snapshots.
- Notification inbox now has a separate quality-gated local-only review section
  and excludes those rows from delivered/would-send/high-priority review queues.
- Quality review and artifact doctor distinguish corrected quality downgrades
  from real stale-route conflicts, while candidate-discovery funnel labels now
  separate resolver attempts, candidate terms, and validated additions.
**Verify:** `python3 tests/test_indicators.py` passed (456/456). Full eval and
verification targets are listed in the final Codex handoff for this prompt.
**Notes/risks:** Research-only. No normal RSI rows, paper/live trades,
execution, alert scoring promotion, provider/LLM promotion, or
LLM/provider-created `TRIGGERED_FADE` behavior changed.

## 2026-06-25 — Make Event Alpha routing obey quality verdicts · Codex
**Why:** Fresh `notify_llm_quality` artifacts could contain a final
`local_only` / `insufficient_data` opportunity verdict while the legacy
watchlist/router path still delivered the row as a research digest. The final
quality verdict must dominate operator-facing routes.
**Changes:**
- Added a router quality gate so alertable Event Alpha routes are downgraded
  when final opportunity metadata says `local_only`, `exploratory`,
  insufficient-data/source-noise/ticker-collision, or zero final opportunity
  score. `TRIGGERED_FADE_RESEARCH` still bypasses this gate only when already
  produced by deterministic `event_fade.py` + `proxy_fade`.
- Persisted route-before/route-after quality-gate metadata, block reasons, and
  final opportunity score/level into route decisions and alert snapshots.
- Added quality-gate downgrade/conflict visibility to router reports, daily
  briefs, research cards, quality review, and artifact doctor.
- Cleaned candidate-discovery funnel counters so raw extracted terms,
  candidate-like terms, resolver-accepted/rejected terms, context-validated
  candidates, and promoted candidates are separated.
**Verify:** `python3 tests/test_indicators.py` passed (456/456). Full eval,
quality-validation, and verification targets are listed in the final Codex
handoff for this prompt.
**Notes/risks:** Research-only. No normal RSI rows, paper/live trades,
execution, alert-scoring promotion, or LLM/provider-created `TRIGGERED_FADE`
behavior changed.

## 2026-06-25 — Add fresh Event Alpha quality coverage profile · Codex
**Why:** Existing `notify_llm` artifacts can contain stale pre-quality-layer
rows, so live-style quality validation needed an isolated profile plus a
strict report that reads raw artifacts instead of compatibility loaders.
**Changes:**
- Added the `notify_llm_quality` Event Alpha profile and no-send scheduled
  target, writing fresh live-style artifacts under
  `event_fade_cache/notify_llm_quality/` without passing the Telegram send flag.
- Added `event_alpha_quality_coverage.py`,
  `main.py --event-alpha-quality-coverage-report`, and
  `make event-alpha-quality-coverage-report` to check latest-run hypothesis,
  watchlist, and alert-snapshot rows for the canonical top-level quality
  fields.
- Added stale-artifact warnings to quality review and impact-hypothesis reports
  when a namespace has missing quality fields while the `quality_validation`
  namespace is clean.
- Updated scheduler awareness, Makefile help, tests, and runbook/decision docs.
**Verify:** `python3 tests/test_indicators.py` passed (455/455) during the
implementation pass. Full eval/verification and fresh `notify_llm_quality`
smoke are listed in the final Codex handoff for this prompt.
**Notes/risks:** Research-only. The new scheduled quality target does not pass
`--event-alert-send`; no normal RSI rows, paper/live trades, execution, or
LLM/provider-created `TRIGGERED_FADE` behavior changed.

## 2026-06-25 — Canonicalize Event Alpha top-level quality artifacts · Codex
**Why:** Fresh quality-validation rows could still carry `None` or empty
top-level signal-quality fields while nested `score_components` made artifact
doctor look healthy. That made Pro-model review and operator audits harder than
they should be.
**Changes:**
- Hardened `event_alpha_quality_fields.ensure_quality_fields` so every new
  hypothesis/watchlist/alert row gets canonical top-level quality fields,
  including conservative local-only defaults plus `upgrade_requirements` and
  `downgrade_warnings`.
- Added strict top-level quality coverage counters to artifact doctor:
  fresh hypothesis/watchlist/alert missing counts are blockers in strict mode,
  while legacy gaps remain warnings.
- Extended quality review, opportunity audit, and policy simulation to prefer
  top-level quality fields, show quality source/coverage, named policy
  scenarios, candidate-discovery funnel details, and weak/generic alertability
  warnings.
- Expanded the signal-quality fixture suite to 21 cases, including explicit
  political meme proxy, CryptoPanic-tagged catalyst, candidate-discovery,
  source URL false positive, and Hyperliquid/HYPE identity cases. Added a
  narrow political meme impact-path rule for explicitly named meme-token event
  mechanics.
- Made `make event-alpha-quality-validation-cycle` clear only the isolated
  `quality_validation` namespace before running and run strict artifact doctor.
**Verify:** `python3 tests/test_indicators.py` (452/452), `python3 main.py
--event-alpha-signal-quality-eval` (21/21), and `make
event-alpha-quality-validation-cycle PYTHON=python3` (strict doctor OK) pass.
Full verification listed in the final Codex handoff for this prompt.
**Notes/risks:** Research-only. No Telegram sends, paper trades, normal RSI
signal rows, execution, or LLM/provider-created `TRIGGERED_FADE` behavior
changed; `TRIGGERED_FADE` remains deterministic `event_fade.py` + `proxy_fade`.

## 2026-06-25 — Validate signal-quality layer + persist upgrade/downgrade paths · Claude
**Why:** Validate the new Event Alpha signal-quality layer against *fresh*
artifacts (uploaded artifacts were stale) and patch only real integration gaps.
**What I found (fresh `quality_validation` namespace cycle, fixture/no-send):**
- The layer is already integrated. Fresh impact-hypothesis rows and
  hypothesis-derived watchlist rows carry the full enforced quality field set
  (impact_path_type/strength, candidate_role, evidence_quality_score,
  source_class, evidence_specificity, market_confirmation_score/level,
  opportunity_score_final/level, opportunity_verdict_reasons, why_local_only,
  why_not_watchlist, manual_verification_items). Alert-snapshot construction
  (`_snapshot_from_route_decision`) includes them too. Artifact doctor reports
  `quality fields: missing_total=0`. Router/verdict behavior passes the 16/16
  signal-quality eval (VELVET/SpaceX, RUNE exploit, ZEC listing, CHZ World Cup →
  watchlist/high-priority; weak BTC quantum/CFTC → local_only/exploratory;
  generic co-occurrence capped at exploratory). Opportunity audit loads by
  symbol/hypothesis_id/alert_id and explains identity→path→evidence→market→
  verdict→router→upgrade/downgrade.
- One genuine gap: `upgrade_requirements`/`downgrade_warnings` were computed
  on-demand in reports but never persisted on hypothesis rows.
**Changes (minimal):**
- `event_impact_hypotheses.py`: added `upgrade_requirements`/`downgrade_warnings`
  to `EventImpactHypothesis`, populated in `_quality_verdict_replace_kwargs` via
  the existing `event_opportunity_verdict.explain_upgrade_path`. They now persist
  on hypothesis rows (and through `event_impact_hypothesis_store`). Pure/diagnostic;
  no routing, send, trade, paper, RSI-write, or `TRIGGERED_FADE` change.
- Added a `quality_validation` fixture profile (offline, no-send) and a
  `make event-alpha-quality-validation-cycle` target that runs a no-send fixture
  cycle + daily brief + quality review + artifact doctor under the
  `quality_validation` namespace for reproducible validation.
- Test: `test_event_impact_hypothesis_persists_upgrade_and_downgrade_paths`.
**Verify:** `.venv/bin/python tests/test_indicators.py` 452/452; `make
event-llm-eval`, `event-llm-extract-eval`, `event-alpha-eval`,
`event-alpha-signal-quality-eval` (16/16), and `make verify` all pass
(`PYTHON=.venv/bin/python`). Fresh cycle wrote under
`event_fade_cache/quality_validation/`; no sends/trades/paper trades occurred.
**Notes/risks:** `python3` in this environment lacks numpy, so the canonical
`.venv/bin/python` interpreter was used. `TRIGGERED_FADE` still comes only from
`event_fade.py` + `proxy_fade`.

## 2026-06-25 — Operationalize Event Alpha signal-quality loop · Codex
**Why:** New live artifacts could still be hard to inspect because quality
fields, candidate-funnel diagnostics, and threshold effects were spread across
several reports. The system needed one artifact-quality loop for daily review
without changing alert/trading behavior.
**Changes:**
- Added shared quality-field enforcement for new hypothesis, watchlist, and
  alert snapshot artifacts, plus artifact-doctor counters for missing quality
  metadata and strict-mode escalation.
- Added `event_alpha_quality_review.py`, `event_alpha_policy_simulator.py`, and
  `event_alpha_signal_quality_export.py` with CLI/Make targets for quality
  review, threshold simulation, and proposed benchmark-case export.
- Extended opportunity audit, daily brief, research cards, and candidate
  discovery funnel reporting with explicit quality summaries, upgrade paths,
  downgrade risks, delivery/feedback context, and conversion counts.
- Added `make event-alpha-quality-loop` / `make event-alpha-quality-loop-llm`
  to run the offline benchmark, quality review, policy simulation, inbox,
  impact-hypothesis report, and daily brief without sending notifications.
**Verify:** `python3 tests/test_indicators.py` (451/451 passed); `make
event-llm-eval PYTHON=python3`; `make event-llm-extract-eval PYTHON=python3`;
`make event-alpha-eval PYTHON=python3`; `make event-alpha-signal-quality-eval
PYTHON=python3`; manual `make event-alpha-quality-loop PROFILE=notify_llm
PYTHON=python3` and `make event-opportunity-audit PROFILE=notify_llm
TARGET=<existing alert id> PYTHON=python3`; `make verify PYTHON=python3`.
**Notes/risks:** Research-only. This does not add live trading, paper trades,
normal RSI signal writes, or any LLM/provider-created `TRIGGERED_FADE`.

## 2026-06-25 — Add Event Alpha signal-quality workbench · Codex
**Why:** Event Alpha needed an offline benchmark and operator audit layer that
answers why a candidate is or is not worth attention, instead of relying on
isolated scoring fields scattered across reports.
**Changes:**
- Added `event_alpha_signal_quality.py` and
  `fixtures/event_discovery/event_alpha_signal_quality_cases.json` with a
  16-case offline benchmark covering proxy exposure, direct token events,
  policy/macro weak co-occurrence, market anomalies, listings/unlocks, and
  common source-noise/word-collision false positives.
- Added `event_opportunity_audit.py`, `--event-opportunity-audit`, and the
  `make event-opportunity-audit` target for candidate-level evidence-chain,
  impact-path, market-confirmation, opportunity-verdict, routing, upgrade, and
  downgrade diagnostics.
- Extended `event_opportunity_verdict.py`, research cards, daily briefs,
  watchlist promotion, router material-change handling, hypothesis reports,
  feedback, and calibration reports with explicit upgrade/downgrade reasoning
  and signal-quality cohorts.
- Added `RSI_EVENT_ALPHA_NOTIFICATION_QUALITY_MODE` so notification profiles
  default to `validated_digest` visibility while keeping exploratory output
  available only when deliberately requested.
**Verify:** `python3 tests/test_indicators.py` (448/448 passed);
`make event-llm-eval PYTHON=python3`; `make event-llm-extract-eval
PYTHON=python3`; `make event-alpha-eval PYTHON=python3`; `make
event-alpha-signal-quality-eval PYTHON=python3`; `make verify PYTHON=python3`.
**Notes/risks:** Research-only. This changes diagnostics, visibility filters,
and watchlist/router metadata for validated hypotheses; it does not add live
trading, paper trades, normal RSI signal writes, or any LLM/provider-created
`TRIGGERED_FADE`.

## 2026-06-25 — Add Event Alpha market/evidence verdict layer · Codex
**Why:** Validated hypotheses needed a stronger attention filter than catalyst
co-occurrence plus impact-path metadata. Operator-facing research digests should
explain market confirmation, source/evidence quality, and final opportunity
verdicts before asking for manual review.
**Changes:**
- Added pure `event_market_confirmation.py`, `event_evidence_quality.py`, and
  `event_opportunity_verdict.py` for bounded market, evidence, and final
  opportunity scoring.
- Integrated the new quality layer into Event Impact Hypothesis validation so
  accepted evidence now carries `market_confirmation_*`,
  `evidence_quality_*`, and `opportunity_score_final` / `opportunity_level`
  metadata beside the existing impact-path fields.
- Updated validated-hypothesis routing to prefer final opportunity verdicts:
  `local_only`/`exploratory` stay local, digest/watchlist levels can enter the
  capped research digest, and high-priority verdicts route to the research
  escalation lane without changing event-fade trigger rules.
- Persisted and surfaced verdict metadata in watchlist rows, alert snapshots,
  impact-hypothesis reports, daily briefs, notification inbox grouping, router
  reports, and research cards.
- Hardened candidate-discovery fallback extraction for explicit crypto project
  mentions while preserving common-word/source-noise rejection reasons.
**Verify:** `python3 tests/test_indicators.py` (442/442 passed);
`python3 -m compileall -q crypto_rsi_scanner tests`; `make event-llm-eval
PYTHON=python3`; `make event-llm-extract-eval PYTHON=python3`; `make
event-alpha-eval PYTHON=python3`; `make verify PYTHON=python3`; manual `make
event-impact-hypothesis-smoke PYTHON=python3`, `make
event-impact-hypotheses-report PROFILE=notify_llm PYTHON=python3`, and `make
event-alpha-notification-inbox PROFILE=notify_llm PYTHON=python3`.
**Notes/risks:** Research-only. This does not add live trading, paper trades,
normal RSI signal writes, or any LLM/provider-created `TRIGGERED_FADE`;
`TRIGGERED_FADE` remains limited to deterministic `event_fade.py` plus
`proxy_fade`.

## 2026-06-25 — Add Event Alpha impact-path validator and v2 digest gate · Codex
**Why:** Recent Event Alpha outputs could still treat “candidate and catalyst
mentioned together” as too similar to evidence that explains a real token,
venue, protocol, or sector impact path. The radar needed stricter quality
metadata before validated hypotheses enter research digests.
**Changes:**
- Added pure `event_impact_path_validator.py` with impact path type, candidate
  role, strength, evidence-specificity scoring, digest eligibility, and
  `opportunity_score_v2` components.
- Routed accepted Event Impact Hypothesis evidence through the new validator so
  RUNE/ZEC/CHZ/VELVET-style rows carry strong/medium path metadata while broad
  BTC quantum/CFTC/policy co-occurrence stays weak/local-only.
- Tightened validated-hypothesis digest routing with
  `RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_MIN_OPPORTUNITY_SCORE`,
  `RSI_EVENT_ALPHA_ALLOW_WEAK_PATH_WITH_MARKET_CONFIRMATION`, and
  `RSI_EVENT_ALPHA_BLOCK_GENERIC_COOCCURRENCE_DIGEST`.
- Persisted the new impact path fields through watchlist rows, alert snapshots,
  hypothesis store reports, daily briefs, notification inbox classification,
  and research cards.
**Verify:** `python3 tests/test_indicators.py` (440/440 passed); `make
event-llm-eval PYTHON=python3`; `make event-llm-extract-eval PYTHON=python3`;
`make event-alpha-eval PYTHON=python3`; `make verify PYTHON=python3`; manual
`make event-impact-hypothesis-smoke PYTHON=python3`, `make
event-impact-hypotheses-report PROFILE=notify_llm PYTHON=python3`, and `make
event-alpha-notification-inbox PROFILE=notify_llm PYTHON=python3`.
**Notes/risks:** Research-only. This does not change normal RSI alerts, paper/
live writes, trading, or the invariant that `TRIGGERED_FADE` only comes from
deterministic `event_fade.py` plus `proxy_fade`.

## 2026-06-24 — Tighten validated hypothesis quality and identity artifacts · Codex
**Why:** Latest `notify_llm` artifacts showed useful validated hypotheses, but
some alert snapshots lacked plain `symbol`/`coin_id`, candidate-discovery
queries were visible without bounded execution, and weak catalyst/token
co-occurrence could still look digest-worthy without a clear impact path.
**Changes:**
- Added the `impact_path_validated` validation stage plus explicit
  `impact_path_reason` diagnostics so RUNE/ZEC/CHZ/VELVET-style rows can pass
  only when evidence explains the token/protocol/venue impact path, while broad
  BTC quantum/CFTC/policy co-occurrence stays local-only by default.
- Tightened validated-hypothesis digest routing with
  `RSI_EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_IMPACT_PATH` and
  `RSI_EVENT_ALPHA_WEAK_VALIDATED_LOCAL_ONLY`; weak validated rows remain
  reviewable in local briefs/inbox/cards with `why_not_promoted` reasons.
- Executed bounded `candidate_discovery` hypothesis-search queries in LLM
  profiles, kept `notify_no_key` limited, and exposed query/result type counts
  in the run ledger and daily brief.
- Persisted plain `symbol`/`coin_id` from validated identity in Event Alpha
  alert snapshots, added a missing-identity warning, and carried
  `impact_path_reason` through watchlist rows, snapshots, cards, reports, and
  inbox output.
- Fixed an anomaly catalyst-search regression where a hypothesis-only config
  reference could be misreported as provider unavailable.
**Verify:** `python3 tests/test_indicators.py` (440/440 passed); `make
event-llm-eval PYTHON=python3`; `make event-llm-extract-eval PYTHON=python3`;
`make event-alpha-eval PYTHON=python3`; `make verify PYTHON=python3`; manual
`make event-impact-hypothesis-smoke PYTHON=python3`, `make
event-impact-hypotheses-report PROFILE=notify_llm PYTHON=python3`, and `make
event-alpha-notification-inbox PROFILE=notify_llm PYTHON=python3`.
**Notes/risks:** Research-only. This does not add live trading, paper trades,
normal RSI signal writes, or any LLM/provider-created `TRIGGERED_FADE`;
`TRIGGERED_FADE` remains limited to deterministic `event_fade.py` plus
`proxy_fade`.

## 2026-06-24 — Gate and persist validated impact hypothesis digests · Codex
**Why:** `notify_llm` could deliver validated impact-hypothesis digest items
without writing corresponding alert snapshots, so the notification inbox had no
per-item feedback queue. Some weak/ambiguous validated hypotheses also needed
stricter digest eligibility before day-1 research notifications.
**Changes:**
- Event Alpha router now applies a configurable validated-hypothesis digest
  quality gate: validated token identity, catalyst-link validation stage,
  source-noise/ticker-collision rejection, minimum hypothesis score, non-
  ambiguous playbook, and either a known external catalyst or explicit direct
  token-event evidence.
- Alert snapshots now include router-approved validated digest decisions even
  when no `EventAlertCandidate` row exists, with route/lane/state/playbook,
  hypothesis metadata, research card path, delivery status, and feedback status
  fields for inbox review.
- Hypothesis watchlist rows now persist richer metadata including
  `hypothesis_id`, `impact_category`, `validation_stage`, `hypothesis_score`,
  `direction_hint`, validated identity, route eligibility, evidence quotes, and
  `why_not_promoted` diagnostics.
- Refined impact-category matching for prediction-market infrastructure,
  tokenized-equity venues, Bitcoin quantum/policy shocks, listings, security
  shocks, and sports/fan-token cases, plus clearer daily brief/card/inbox copy.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`; `python3
tests/test_indicators.py` (439/439 passed); `make event-llm-eval
PYTHON=python3`; `make event-llm-extract-eval PYTHON=python3`; `make
event-alpha-eval PYTHON=python3`; `make verify PYTHON=python3`; manual `make
event-impact-hypothesis-smoke PYTHON=python3`, `make
event-impact-hypotheses-report PROFILE=notify_llm PYTHON=python3`, and `make
event-alpha-notification-inbox PROFILE=notify_llm PYTHON=python3` smoke checks.
**Notes/risks:** This remains research-only. It does not add live trading,
paper trades, normal RSI signal writes, or any LLM/provider-created
`TRIGGERED_FADE`; `TRIGGERED_FADE` remains limited to deterministic
`event_fade.py` plus `proxy_fade`.

## 2026-06-24 — Promote validated impact hypotheses safely · Codex
**Why:** Recent Event Impact Hypothesis artifacts showed two correctness gaps:
validated token-level hypotheses could use the first taxonomy candidate instead
of the actually validated asset, and validated `RADAR` hypotheses remained
invisible in day-1 research notifications.
**Changes:**
- Event Impact Hypothesis watchlist rows now select token identity from
  validated asset evidence first, warn on candidate-order mismatches, and fall
  back to `SECTOR` when validation lacks a real token identity.
- Added a capped daily-digest route for validated token-level impact hypotheses
  in notification profiles. The copy and research cards label these as
  research-only validated impact hypotheses, not trade signals or calibrated
  strategies.
- Refined impact category validation so prediction-market infrastructure,
  tokenized-equity venues, miner listings, security shocks, and fan/sports
  events land in their intended categories instead of broad false-positive
  buckets.
- Made impact-hypothesis reports latest-run-first by default, with
  `--all-history` / `ALL_HISTORY=1` for historical rows, and surfaced digest
  eligibility plus mismatch warnings.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`; `python3
tests/test_indicators.py` (438/438 passed); `make event-llm-eval
PYTHON=python3`; `make event-llm-extract-eval PYTHON=python3`; `make
event-alpha-eval PYTHON=python3`; `make verify PYTHON=python3`; `make
event-impact-hypothesis-smoke PYTHON=python3`; `make
event-impact-hypotheses-report PROFILE=notify_llm PYTHON=python3`.
**Notes/risks:** This only makes validated `RADAR` hypotheses visible in a
capped daily research digest. It does not create `WATCHLIST`, `HIGH_PRIORITY`,
paper/live rows, normal RSI rows, trading actions, or `TRIGGERED_FADE`.

## 2026-06-24 — Make LLM notification profiles send every clean run · Codex
**Why:** The first post-parallelism `notify_llm` run completed successfully but
Telegram delivery was held by a 24h exploratory-digest cooldown from the prior
run. The owner wants operator-visible notifications every time the system runs.
**Changes:**
- Updated `notify_llm` and `notify_llm_deep` to mirror the per-run delivery
  policy already used by `notify_no_key`: heartbeat/digest/exploratory
  cooldowns are zero and content dedupe is disabled while run locks and
  in-flight delivery safety remain active.
- Updated the scheduled notification Make target so `notify_llm` and
  `notify_llm_deep` use a zero content-dedupe window instead of the default 24h
  dedupe.
- Documented the per-run LLM notification policy in `.env.example` and the
  Event Alpha runbook.
- Added regression coverage for LLM profile cooldown/dedupe defaults and
  scheduled Make target output.
**Verify:** `python3 tests/test_indicators.py` (435/435 passed); `python3 -m
compileall -q crypto_rsi_scanner tests`; `make event-alpha-eval PYTHON=python3`;
`make verify PYTHON=python3`; `RSI_EVENT_ALERTS_ENABLED=1 make
event-alpha-notify-llm-scheduled PYTHON=python3`.
**Notes/risks:** Delivery-frequency policy only. This does not change Event
Alpha scoring, alertability, normal RSI rows, paper/live writes, trading, or
`TRIGGERED_FADE` eligibility.

## 2026-06-24 — Parallelize Event Alpha LLM calls for notification runs · Codex
**Why:** Sequential OpenAI extraction/relationship calls made `notify_llm`
runs vulnerable to one slow request delaying the whole batch. The owner is
comfortable with a longer overall run if it produces better LLM coverage.
**Changes:**
- Added bounded parallel provider execution to raw-event LLM extraction and
  relationship analysis while preserving cache hits, budget accounting,
  runtime-deadline skips, and deterministic report row ordering.
- Added `RSI_EVENT_LLM_MAX_PARALLEL_CALLS` config and local profile override
  support, then raised OpenAI-backed Event Alpha profiles: `notify_llm` now uses
  12 parallel LLM calls, 30s relationship/extraction HTTP timeouts, and a 600s
  notification runtime budget; `notify_llm_deep` uses 16 parallel calls and
  45s LLM timeouts.
- Expanded Event Alpha status/profile reporting and `.env.example` docs to show
  LLM parallelism, timeouts, and notification runtime caps.
- Added regression coverage proving relationship analysis and raw-event
  extraction actually run with bounded parallel overlap.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`;
`python3 tests/test_indicators.py` (435/435 passed); `make event-llm-eval
PYTHON=python3`; `make event-llm-extract-eval PYTHON=python3`; `make
event-alpha-eval PYTHON=python3`; `make verify PYTHON=python3`.
**Notes/risks:** Runtime/coverage improvement only. This does not change Event
Alpha scoring, alert routing, Telegram send guards, normal RSI rows, paper/live
writes, trading, or `TRIGGERED_FADE` eligibility.

## 2026-06-23 — Guard OpenAI LLM loops with notification runtime deadlines · Codex
**Why:** A full `notify_llm` run showed the GDELT fetch cap was fixed, but slow
OpenAI raw-event extraction calls could still keep running past the
notification cycle's runtime budget because the deadline was only checked
between pipeline stages.
**Changes:**
- Added runtime-deadline support to the raw-event LLM extractor and relationship
  analyzer configs.
- Taught both LLM loops to reuse cache hits but skip new uncached provider calls
  once the notification runtime deadline is exhausted.
- Wired the notification cycle's max-runtime deadline into OpenAI-backed LLM
  extraction and relationship analysis.
- Added regression coverage proving expired deadlines skip uncached provider
  calls in both LLM paths.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`;
`python3 tests/test_indicators.py` (433/433 passed); `make event-llm-eval
PYTHON=python3` (9/9 passed); `make event-llm-extract-eval PYTHON=python3`
(7/7 passed); `make event-alpha-eval PYTHON=python3` (11/11 passed); `make
verify PYTHON=python3`.
**Notes/risks:** Reliability guard only. This does not change Event Alpha
scoring, source/provider selection, Telegram guard semantics, normal RSI rows,
paper/live writes, trading, or `TRIGGERED_FADE` eligibility.

## 2026-06-23 — Cap live GDELT catalyst-search fetches per run · Codex
**Why:** A live notification run exposed an operational hang: GDELT catalyst
search fetched once per hypothesis/query and kept retrying through 429/timeouts,
making `notify_llm`/`notify_no_key` runs too slow to finish reliably.
**Changes:**
- Added a per-search fetch cap to event-provider catalyst search adapters and
  set GDELT catalyst search to one live fetch per provider search before local
  filtering/backoff takes over.
- Propagated live provider `last_warnings` into catalyst-search results so the
  provider health wrapper can record backoff immediately.
- Added regression coverage proving repeated GDELT catalyst queries perform only
  one live fetch when the provider is failing.
**Verify:** `python3 tests/test_indicators.py` (431/431 passed); `python3 -m compileall -q crypto_rsi_scanner tests`; `make event-llm-eval PYTHON=python3` (9/9 passed); `make event-llm-extract-eval PYTHON=python3` (7/7 passed); `make event-alpha-eval PYTHON=python3` (11/11 passed); `make verify PYTHON=python3`; `RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-notify-no-key-scheduled PYTHON=python3` completed and delivered Telegram heartbeat + exploratory digest.
**Notes/risks:** Research notification reliability only. This does not change
alert scoring, watchlist promotion, normal RSI rows, paper/live writes, trading,
or `TRIGGERED_FADE` eligibility.

## 2026-06-23 — Raise Event Alpha LLM budget controls · Codex
**Why:** The OpenAI-backed Event Alpha notification profiles were too shallow
for the owner's desired daily runs: `notify_llm` only allowed 10 calls per run
and 50 per day, while local `.env` budget values were ignored by profile
overrides.
**Changes:**
- Raised checked-in LLM profile defaults for `full_llm_live`, `notify_llm`, and
  `notify_llm_deep`, including relationship candidates, raw-event extraction
  events, per-run calls, per-day calls, and estimated daily cost caps.
- Let local `RSI_EVENT_LLM_*` budget env vars override profile budget defaults
  at runtime without changing non-budget profile semantics.
- Expanded Event Alpha status/profile reporting and `.env.example` docs to show
  candidate/extractor caps as well as call/day/cost/cache caps.
- Added regression coverage proving local LLM budget env values win for
  `notify_llm`.
**Verify:** `python3 tests/test_indicators.py` (430/430 passed); `python3 -m compileall -q crypto_rsi_scanner tests`; `make event-llm-eval PYTHON=python3` (9/9 passed); `make event-llm-extract-eval PYTHON=python3` (7/7 passed); `make event-alpha-eval PYTHON=python3` (11/11 passed); `make verify PYTHON=python3`; `python3 main.py --event-alpha-status --event-alpha-profile notify_llm`.
**Notes/risks:** Budget controls only affect how much LLM analysis/extraction is
attempted. This does not change alert scoring, Telegram safety guards, normal
RSI alerts, paper/live writes, trading, or `TRIGGERED_FADE` eligibility.

## 2026-06-23 — Make impact hypothesis reports latest-run diagnosable · Codex
**Why:** `notify_llm` artifacts could mix old legacy rows with fresh hypothesis
rows, making the report look like current runs had `validation_stage=unknown`
and hiding why search evidence failed validation.
**Changes:**
- Added latest-run, run-id, since, and legacy-aware loading/report filters for
  `event_impact_hypotheses.jsonl`, plus schema, query, entity, and historical
  row summaries.
- Stored generated vs executed hypothesis queries separately and widened
  candidate-discovery query visibility while preserving candidate-specific
  validation queries.
- Persisted `result_score` in rejected validation samples, summarized rejected
  evidence reasons/titles in the daily brief, and surfaced suspicious external
  entities that appear as crypto candidates.
- Added `event-alpha-notify-llm-deep-scheduled` for the bounded
  `notify_llm_deep` profile and Make report variables `LATEST`, `RUN_ID`, and
  `SINCE`.
- Updated tests, `ROADMAP.md`, `DECISIONS.md`, and
  `research/EVENT_ALPHA_RUNBOOK.md`.
**Verify:** `python3 tests/test_indicators.py` (430/430 passed); `python3 -m
compileall -q crypto_rsi_scanner tests`; `make event-llm-eval PYTHON=python3`
(9/9 passed); `make event-llm-extract-eval PYTHON=python3` (7/7 passed);
`make event-alpha-eval PYTHON=python3` (11/11 passed); `make verify
PYTHON=python3`; `make event-impact-hypothesis-smoke PYTHON=python3`; `make
event-impact-hypotheses-report PROFILE=notify_llm PYTHON=python3`; `make
event-impact-hypotheses-report PROFILE=notify_llm LATEST=1 PYTHON=python3`.
**Notes/risks:** Observability/reporting only. This does not change alert
promotion, Telegram routing, paper/live writes, normal RSI signal rows, or the
rule that `TRIGGERED_FADE` only comes from `event_fade.py` plus `proxy_fade`.

## 2026-06-23 — Make impact hypotheses promotion-auditable · Codex
**Why:** The impact-hypothesis layer needed to turn sector/catalyst intelligence
into useful RADAR candidates without letting discovery-only evidence look
validated. It also needed clearer artifact diagnostics for legacy rows, missing
schema fields, rejected evidence, and why a hypothesis did not promote.
**Changes:**
- Added `why_not_promoted` diagnostics to impact hypotheses and surfaced reason
  counts in local hypothesis reports and daily briefs.
- Expanded candidate-discovery query templates for external catalysts and let
  candidate-discovery search results suggest crypto assets while still requiring
  deterministic identity+catalyst validation before token-level `RADAR`.
- Added schema-audit reporting for stored hypothesis artifacts, including
  legacy row counts and missing `validation_stage`, `hypothesis_score`,
  `external_entities`, and `crypto_candidate_assets` fields.
- Tightened rejected-validation sample display so accepted validation evidence
  is not presented as rejected, and added regression coverage for external
  entity filtering, candidate-discovery validation, schema diagnostics, and
  source-enrichment cleanup preserving legitimate HYPE/Hyperliquid text.
- Updated `DECISIONS.md`, `ROADMAP.md`, and `research/EVENT_ALPHA_RUNBOOK.md`.
**Verify:** `python3 tests/test_indicators.py` (429/429 passed); `make
event-llm-eval PYTHON=python3` (9/9 passed); `make event-llm-extract-eval
PYTHON=python3` (7/7 passed); `make event-alpha-eval PYTHON=python3` (11/11
passed); `make event-impact-hypothesis-smoke PYTHON=python3`; `make
event-impact-hypotheses-report PROFILE=notify_llm PYTHON=python3`; `make
verify PYTHON=python3`.
**Notes/risks:** Research-only semantics remain unchanged. Candidate-discovery
hits are suggestions, not alerts; `TRIGGERED_FADE` still only comes from
`event_fade.py` plus `proxy_fade`.

## 2026-06-23 — Make notify_no_key send every clean run · Codex
**Why:** The owner wants Telegram visibility whenever the Event Alpha system
runs, not only when a lane cooldown or content-dedupe window allows a digest.
**Changes:**
- Updated the `notify_no_key` profile so daily, instant, heartbeat, and
  exploratory digest cooldowns are zero and content dedupe is disabled.
- Kept overlap/in-flight safeguards active through the existing run lock and
  delivery ledger, and aligned the scheduled Make target with the no-dedupe
  delivery policy.
- Documented the per-run delivery decision in `DECISIONS.md`, `ROADMAP.md`,
  `.env.example`, and `research/EVENT_ALPHA_RUNBOOK.md`.
**Verify:** `python3 tests/test_indicators.py` (426/426 passed); `make
event-llm-eval PYTHON=python3` (9/9 passed); `make event-llm-extract-eval
PYTHON=python3` (7/7 passed); `make event-alpha-eval PYTHON=python3` (11/11
passed); `make verify PYTHON=python3`; live `RSI_EVENT_ALERTS_ENABLED=1 make
event-alpha-notify-no-key PYTHON=python3 IGNORE_BACKOFF=1` delivered 2
Telegram records (`exploratory_digest` and `health_heartbeat`) with 0 failed,
0 duplicate, 0 in-flight, and 0 blocked deliveries.
**Notes/risks:** This is delivery frequency only. It does not change Event Alpha
scoring, normal RSI alert routing, paper/live writes, trading, or the rule that
`TRIGGERED_FADE` only comes from deterministic `event_fade.py` plus
`proxy_fade`.

## 2026-06-23 — Clean Event Impact Hypothesis semantics · Codex
**Why:** Pro-model review flagged that external catalysts, candidate crypto
assets, and validation-search outcomes were still too easy to blur together.
That could make sector intelligence look like token-level evidence.
**Changes:**
- Split impact hypotheses into external entities, crypto candidate assets, and
  rejected candidate assets so companies such as OpenAI/SpaceX stay out of
  token `candidate_symbols`.
- Added hypothesis scores, score components, typed validation stages, typed
  search-query metadata, granular candidate/identity/catalyst validation, and
  capped rejected validation evidence samples.
- Allowed sector hypotheses to generate candidate-discovery queries while
  keeping token-level RADAR promotion gated on catalyst-linked validation.
- Updated hypothesis reports, stored artifacts, daily brief copy, and watchlist
  score metadata to show scores/stages/entities/candidates/rejections.
- Hardened source enrichment text extraction against ticker tape, nav/menu,
  footer, and generic price-table noise.
**Verify:** `python3 tests/test_indicators.py` (425/425 passed); `make
event-llm-eval PYTHON=python3` (9/9 passed); `make event-llm-extract-eval
PYTHON=python3` (7/7 passed); `make event-alpha-eval PYTHON=python3` (11/11
passed); `make verify PYTHON=python3`.
**Notes/risks:** Research-only semantics. This does not change normal RSI
alerts, paper/live writes, trading, event-fade eligibility, or the rule that
`TRIGGERED_FADE` only comes from `event_fade.py` plus `proxy_fade`.

## 2026-06-23 — Harden notification provider failure handling · Codex
**Why:** A fresh `notify_llm` run surfaced provider/runtime problems: GDELT was
rate-limited, one public RSS feed returned 403, and live OpenAI calls could
consume too much notification-cycle runtime. The upstream rate limit should stay
visible, but partial provider failures should not disable useful sources or hang
the cycle.
**Changes:**
- Added explicit `RSI_EVENT_LLM_OPENAI_TIMEOUT` and
  `RSI_EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT` config, wired through OpenAI
  relationship/extraction providers, and set conservative caps in OpenAI-backed
  Event Alpha profiles.
- Adjusted event-provider health so multi-feed RSS `feed_failure` warnings are
  still reported but do not trip provider backoff when the provider returned
  useful rows from another feed.
- Added regression coverage for RSS partial-feed provider health and OpenAI
  timeout propagation.
- Documented the new timeout knobs in `.env.example`.
**Verify:** `python3 tests/test_indicators.py` (424/424 passed); `make
event-llm-eval PYTHON=python3` (9/9 passed); `make event-llm-extract-eval
PYTHON=python3` (7/7 passed); `make event-alpha-eval PYTHON=python3` (11/11
passed); `make verify PYTHON=python3`.
**Notes/risks:** GDELT `429` remains an upstream rate-limit/backoff condition;
this change does not suppress that warning or bypass provider health. Research
notifications remain guarded and no trading, paper trades, normal RSI writes, or
LLM-created `TRIGGERED_FADE` paths changed.

## 2026-06-23 — Polish Event Impact Hypothesis review artifacts · Codex
**Why:** The hypothesis layer already persisted profile-scoped rows, but the
review artifacts needed flatter validated-asset fields, explicit promotion keys,
and a focused inbox so operators and Pro-model reviews can quickly separate
pending, validated, rejected, and stale hypotheses.
**Changes:**
- Extended `event_impact_hypothesis_store.py` rows with
  `candidate_sources`, `validated_symbol`, `validated_coin_id`, and
  `promoted_watchlist_key`, and expanded the report with pending/validated/
  rejected/query/promotion/stale sections.
- Added `format_impact_hypotheses_inbox()`,
  `main.py --event-impact-hypotheses-inbox`, and
  `make event-impact-hypotheses-inbox`.
- Updated Event Alpha daily briefs to summarize stored hypothesis rows directly
  when available.
- Added regression coverage for the new flattened fields, report sections, and
  inbox review buckets.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`;
`python3 tests/test_indicators.py` (423/423 passed); `make event-llm-eval
PYTHON=python3` (9/9 passed); `make event-llm-extract-eval PYTHON=python3`
(7/7 passed); `make event-alpha-eval PYTHON=python3` (11/11 passed);
`make event-impact-hypothesis-smoke PYTHON=python3`; `make
event-impact-hypotheses-report PROFILE=notify_llm PYTHON=python3`; `make
event-impact-hypotheses-inbox PROFILE=notify_llm PYTHON=python3`; `make verify
PYTHON=python3`.
**Notes/risks:** Artifact/report-only change. No Event Alpha alert tiering,
Telegram delivery, paper/live writes, normal RSI routing, event-fade eligibility,
or `TRIGGERED_FADE` authority changed.

## 2026-06-23 — Persist Event Impact Hypotheses · Codex
**Why:** The Event Impact Hypothesis layer was useful in console/run summaries,
but the Pro-review workflow needs inspectable, profile-scoped artifact rows that
explain candidate provenance, validation status, search diagnostics, and
watchlist promotion links.
**Changes:**
- Added `event_impact_hypothesis_store.py` and wired Event Alpha cycles and
notification cycles to append `event_impact_hypotheses.jsonl` rows under the
active artifact namespace.
- Added hypothesis store/report plumbing, `--event-impact-hypotheses-report`,
`make event-impact-hypotheses-report`, and an offline
`--event-impact-hypothesis-smoke` / `make event-impact-hypothesis-smoke` path
that validates SpaceX → VELVET RADAR while preserving no-trigger safety.
- Extended impact hypotheses with `suggested_candidate_assets`,
`validated_candidate_assets`, and `candidate_source`; LLM-extracted assets
remain suggestions until deterministic validation confirms identity.
- Split hypothesis-search skip reasons from market-anomaly catalyst-search
reasons in pipeline reports, run-ledger rows/reports, and daily briefs.
- Enabled bounded full-source enrichment only for `notify_llm`, added an
opt-in `notify_llm_deep` profile, and left `notify_no_key` no-key/no-full-source
by default.
- Updated `.env.example`, `ROADMAP.md`, `DECISIONS.md`,
`research/EVENT_ALPHA_RUNBOOK.md`, and Makefile help/targets.
**Verify:** `python3 tests/test_indicators.py` (422/422 passed);
`python3 -m compileall -q crypto_rsi_scanner tests`; `make event-llm-eval
PYTHON=python3` (9/9 passed); `make event-llm-extract-eval PYTHON=python3`
(7/7 passed); `make event-alpha-eval PYTHON=python3` (11/11 passed); `make
event-impact-hypothesis-smoke PYTHON=python3`; `make
event-impact-hypotheses-report PROFILE=notify_llm PYTHON=python3`; `make verify
PYTHON=python3`.
**Notes/risks:** Research artifacts only. Hypothesis rows do not create
`WATCHLIST`, `HIGH_PRIORITY`, `TRIGGERED_FADE`, paper trades, live signal rows,
normal RSI routing, or execution; `TRIGGERED_FADE` remains only from
`event_fade.py` + `proxy_fade`.

## 2026-06-23 — Require zip handoff after commit/push · Codex
**Why:** The human shares this project with a Pro model for review and wants a
fresh source-plus-artifacts zip after every pushed change.
**Changes:**
- Updated `AGENTS.md` so Codex and Claude should provide a fresh project zip
  after each successful commit + push.
- Clarified that the zip should include current source plus local research
  artifacts such as `event_fade_cache/`, while excluding secrets and
  machine-local noise like `.env`, DBs, logs, `.venv`, `.git`, IDE files, and
  caches.
**Verify:** `make verify PYTHON=python3`.
**Notes/risks:** Protocol-only change; no scanner logic changed.

## 2026-06-23 — Harden Event Alpha impact discovery · Codex
**Why:** Impact hypotheses were useful, but broad substring rules and immediate
sector-to-token watchlist identity could create misleading CHZ/HYPE/VELVET-style
rows before source evidence validated the specific asset.
**Changes:**
- Replaced loose impact-hypothesis substring matching with boundary/phrase-aware
  category rules and tighter context checks for sports, political, prediction
  market infrastructure, stablecoin regulatory, and tokenized/pre-IPO catalyst
  hypotheses.
- Added `hypothesis_scope` (`sector`, `token`, `venue`, `infrastructure`) so
  unvalidated sector/venue/infra hypotheses persist as `SECTOR` rows while
  candidate symbols remain metadata for validation searches.
- Added separate impact-hypothesis validation search execution using the
  catalyst-search provider layer, with identity-required result scoring and
  separate pipeline report metrics from market-anomaly catalyst search.
- Wired source enrichment into the Event Alpha operating cycle before LLM raw
  extraction, so quote-validated extraction can use full fetched source text.
- Enabled hypothesis validation search for `notify_no_key`/`notify_llm` profiles
  while leaving default config disabled, and made `notify_llm` explicitly enable
  CryptoPanic as optional live source evidence.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`;
`python3 tests/test_indicators.py` (418/418 passed).
**Notes/risks:** Research-only hardening. This does not change normal RSI
alerts, event-fade eligibility, Telegram send guards, paper trades, live signal
writes, or execution. `TRIGGERED_FADE` remains only from `event_fade.py` +
`proxy_fade`.

## 2026-06-23 — Harden Event Alpha source intake observability · Codex
**Why:** The Event Alpha intelligence layer could generate hypotheses, but
zero-query catalyst-search runs and RSS feed failures needed clearer
operator-facing explanations so “no alertable candidates” can be debugged
without weakening research-only safety gates.
**Changes:**
- Made live RSS feed handling distinguish per-feed `feed_failure` rows from
  provider-level `provider_failure` rows. HTTP 403/404-style feed failures no
  longer stop the remaining RSS feeds even when fail-fast is enabled; broad
  provider/network failures can still stop the bundle when configured.
- Added catalyst-search `skip_reasons` counters for disabled profiles,
  provider unavailability/backoff, below-threshold anomalies, missing anomaly
  identity, runtime budget exhaustion, zero query limits, and unknown
  zero-query states.
- Surfaced catalyst-search skip reasons in the Event Alpha pipeline report,
  run ledger, run-ledger report, and daily brief.
- Updated `notify_llm` to include CryptoPanic in the catalyst-search provider
  bundle while leaving `notify_no_key` on no-key providers.
- Added offline regression tests for RSS partial feed failure behavior and
  catalyst-search skip-reason flow through ledger and brief artifacts.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`;
`python3 tests/test_indicators.py` (415/415 passed); `make event-llm-eval
PYTHON=python3` (9/9 passed); `make event-llm-extract-eval PYTHON=python3`
(7/7 passed); `make event-alpha-eval PYTHON=python3` (11/11 passed);
`make verify PYTHON=python3`.
**Notes/risks:** Metadata-only hardening. This does not change Event Alpha
alert tiering, event-fade eligibility, Telegram send guards, paper trades,
normal RSI signal writes, or execution.

## 2026-06-23 — Add Event Alpha impact hypotheses · Codex
**Why:** Live Event Alpha artifacts were safely producing mostly
`RAW_EVIDENCE` / `STORE_ONLY` rows, but the radar lacked an intermediate layer
that says which sectors/assets an external catalyst might impact before direct
asset validation exists.
**Changes:**
- Added `event_impact_hypotheses.py` with deterministic impact categories,
  hypothesis statuses, taxonomy loading, search-query generation, identity-safe
  validation, and a local report formatter.
- Added the fixture taxonomy
  `fixtures/event_discovery/event_impact_taxonomy.json` for tokenized-stock
  venues, prediction markets, fan tokens, stablecoin/RWA, AI tokens, perp DEXes,
  and oracle infrastructure.
- Added `HYPOTHESIS` watchlist state plus hypothesis watchlist persistence;
  unvalidated hypotheses are store-only/exploratory, while validated evidence
  can promote a hypothesis row to `RADAR` without creating `TRIGGERED_FADE`.
- Wired hypothesis counts/reporting into the Event Alpha pipeline, run ledger,
  daily brief, router suppression, and exploratory Telegram digest copy.
- Added `event_source_enrichment.py` for optional cached full-content source
  enrichment and made LLM extraction packets use enriched source text when
  present in raw event metadata.
- Documented disabled-by-default impact taxonomy and source-enrichment env
  knobs in `.env.example`.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`;
`python3 tests/test_indicators.py` (414/414 passed); `make event-llm-eval
PYTHON=python3` (9/9 passed); `make event-llm-extract-eval PYTHON=python3`
(7/7 passed); `make event-alpha-eval PYTHON=python3` (11/11 passed);
`make verify PYTHON=python3`.
**Notes/risks:** This is still research-only. Hypotheses are not trades, paper
trades, normal RSI rows, or event-fade triggers. `TRIGGERED_FADE` remains
reserved for `event_fade.py` plus the `proxy_fade` playbook.

## 2026-06-22 — Make exploratory Telegram digest readable · Codex
**Why:** The Event Alpha exploratory Telegram digest was technically complete
but hard to use: each row dumped internal IDs, card paths, feedback commands,
suppression enums, and repeated boilerplate instead of a concise research
summary.
**Changes:**
- Reworked `format_exploratory_telegram_digest()` to render one compact
  disclaimer/header, numbered candidate blocks, human playbook/status labels,
  move and volume/mcap summaries, manual verification steps, and concise risk
  notes.
- Hid Telegram-only noise such as `alert_id`, `card_id`, local research-card
  paths, raw feedback commands, and pipe-delimited internal IDs while leaving
  those fields available in artifacts/inbox reports.
- Added Telegram formatting regressions covering hidden internals, one-time
  disclaimer copy, compact numbered blocks, and size-safe truncation.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`;
`python3 tests/test_indicators.py` (410/410 passed); `make event-alpha-eval
PYTHON=python3` (11/11 passed); `make verify PYTHON=python3`.
**Notes/risks:** Formatting-only change. Event Alpha selection, routing,
scoring, alertability, `TRIGGERED_FADE` authority, paper/live writes, and normal
RSI alert routing were not changed.

## 2026-06-22 — Add exploratory Event Alpha notification digest · Codex
**Why:** Day-1 Event Alpha notifications needed a way to surface suppressed,
store-only, and low-confidence research rows without promoting them into normal
alertable lanes or making them look like trades.
**Changes:**
- Added a separate `exploratory_digest` notification lane with its own config,
  profile defaults, cooldown/dedupe handling, blocked-delivery accounting, and
  Telegram copy that labels rows as unvalidated research evidence.
- Wired exploratory candidates into notification planning, daily briefs, inbox
  review, run output, and `notify_no_key`/`notify_llm` profiles while keeping
  alertable instant/daily/triggered lanes unchanged.
- Added a guarded per-recipient Telegram diagnostic command and Make target so
  operators can verify individual chat delivery without exposing chat IDs.
- Documented the new lane, recipient check, optional CryptoPanic source warning,
  and research-only boundaries in the runbook, roadmap, decisions, and env
  example.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests`;
`python3 tests/test_indicators.py` (409/409 passed); `make event-llm-eval
PYTHON=python3` (9/9 passed); `make event-llm-extract-eval PYTHON=python3`
(7/7 passed); `make event-alpha-eval PYTHON=python3` (11/11 passed);
`make verify PYTHON=python3`; `make -n event-alpha-telegram-recipient-check
PROFILE=notify_no_key PYTHON=python3`; no-send notify-cycle smoke under `/tmp`;
blocked would-send notify-cycle smoke under `/tmp` recorded 1 blocked
exploratory digest and no actual sends.
**Notes/risks:** The exploratory digest is review-only. It cannot create
`TRIGGERED_FADE`, write paper/live rows, or route normal RSI alerts; source-noise
and ticker-collision controls are excluded by default unless explicitly enabled.

## 2026-06-21 — Fix notification SLO latest-run status selection · Codex
**Why:** A full `notify_llm` run delivered its guarded health heartbeat, but the
SLO report still showed `NO_SEND_CONFIG` because an older no-send bootstrap row
was counted as a current status. Historical config-blocked rows should remain
visible as warnings, not override a newer successful delivery.
**Changes:**
- Updated `event_alpha_notification_slo.py` so run classification tracks the
  latest meaningful send status and only uses that latest status to select
  `NO_SEND_CONFIG`.
- Kept historical `config_blocked_runs` and no-send preview counts in the SLO
  report as warning/accounting fields.
- Added a regression test covering an older config-blocked run followed by a
  newer delivered heartbeat.
**Verify:** `python3 tests/test_indicators.py` (405/405 passed);
`make event-llm-eval PYTHON=python3`; `make event-llm-extract-eval
PYTHON=python3`; `make event-alpha-eval PYTHON=python3`; `make verify
PYTHON=python3`; `make event-alpha-notification-slo-report PROFILE=notify_llm
PYTHON=python3`; `make event-alpha-notification-slo-report PROFILE=notify_no_key
PYTHON=python3`.
**Notes/risks:** The latest live `notify_llm` run sent one research heartbeat to
Telegram and generated no alertable trading candidates. GDELT/RSS providers are
still degraded from upstream 429/403 responses.

## 2026-06-20 — Polish Event Alpha notification SLO semantics · Codex
**Why:** The notification SLO report was treating would-send/no-send preview
runs as alertable undelivered delivery failures, which made intentional dry runs
look like Telegram outages.
**Changes:**
- Added `NO_SEND_CONFIG` SLO status and split run categories in
  `event_alpha_notification_slo.py`: `no_send_preview_runs`,
  `config_blocked_runs`, `delivery_failed_runs`, and
  `alertable_delivery_failures`.
- Updated notification-run rows to persist `send_requested`,
  `send_attempted`, and `send_success` so future SLO reports can distinguish
  preview/config states from sender delivery failures.
- Added regression tests for preview would-send rows, config-blocked sends,
  guard-enabled delivery failures, delivered heartbeat OK state, and provider
  backoff with no send. Updated `ROADMAP.md`, `DECISIONS.md`, and the Event
  Alpha runbook.
**Verify:** `python3 tests/test_indicators.py` (405/405 passed);
`make event-llm-eval PYTHON=python3`; `make event-llm-extract-eval
PYTHON=python3`; `make event-alpha-eval PYTHON=python3`; `make verify
PYTHON=python3`; `python3 main.py --event-alpha-notification-slo-report
--event-alpha-profile notify_no_key`.
**Notes/risks:** Existing legacy notification rows without `send_requested`
default to preview/no-send semantics instead of delivery failure. This is
intentional for day-1 burn-in safety.

## 2026-06-20 — Add scheduled Event Alpha notification ops guardrails · Codex
**Why:** Scheduled day-1 Event Alpha research notifications needed better
operator controls before launchd/cron burn-in: a redacted environment doctor,
explicit emergency pause, freshness/SLO checks, and a clean handoff pack.
**Changes:**
- Added `event_alpha_environment_doctor.py`, `event_alpha_scheduler.py`,
  `event_alpha_notification_slo.py`, `event_alpha_notification_pause.py`, and
  `event_alpha_notification_pack.py`.
- Wired new CLI/Make surfaces:
  `--event-alpha-environment-doctor`, `--event-alpha-pause-notifications`,
  `--event-alpha-resume-notifications`, `--event-alpha-scheduler-status`,
  `--event-alpha-generate-launchd`,
  `--event-alpha-notification-slo-report`, and
  `--event-alpha-export-notification-pack`.
- Added `RSI_EVENT_ALPHA_NOTIFICATIONS_PAUSED` and
  `RSI_EVENT_ALPHA_NOTIFICATIONS_PAUSE_REASON`; paused sends still write
  blocked delivery rows with `error_class=notifications_paused` and do not
  block discovery/report artifacts.
- Updated `.env.example`, `ROADMAP.md`, `DECISIONS.md`, and
  `research/EVENT_ALPHA_RUNBOOK.md`; added offline regression tests for doctor
  blockers, pause/resume, scheduler status, SLO status, redacted pack export,
  and Make target wiring.
**Verify:** `python3 tests/test_indicators.py` (404/404 passed);
`python3 -m compileall -q crypto_rsi_scanner tests`; `make event-llm-eval
PYTHON=python3`; `make event-llm-extract-eval PYTHON=python3`; `make
event-alpha-eval PYTHON=python3`; `make verify PYTHON=python3`; `make
event-alpha-notify-fixture-smoke PYTHON=python3`; `python3 main.py
--event-alpha-notification-deliveries-report --event-alpha-profile fixture
--event-alpha-artifact-namespace fixture_notify_smoke`; `python3 main.py
--event-alpha-notify-go-no-go --event-alpha-profile notify_no_key`;
`python3 main.py --event-alpha-environment-doctor --event-alpha-profile
notify_no_key`; `python3 main.py --event-alpha-scheduler-status
--event-alpha-profile notify_no_key`; `python3 main.py
--event-alpha-notification-slo-report --event-alpha-profile notify_no_key`;
`python3 main.py --event-alpha-export-notification-pack --event-alpha-profile
notify_no_key --out /tmp/event_alpha_notification_pack_verify.zip`.
**Notes/risks:** The repeated fixture smoke wrote a duplicate-skip row because
the fixture namespace already had delivered rows; the delivery report confirmed
the previous delivered rows and the expected dedupe. This remains research-only:
no live trading, paper trades, normal RSI signal writes, or LLM-created
`TRIGGERED_FADE`; `TRIGGERED_FADE` remains owned by `event_fade.py` +
`proxy_fade`.

## 2026-06-20 — Polish Event Alpha day-1 notification fidelity · Codex
**Why:** Day-1 Event Alpha notifications needed more faithful delivery state and
clearer operator UX before unattended research burn-in: Telegram partial sends
were too easy to confuse with total failures, and timestamped heartbeats/digests
needed stable dedupe keys independent of exact rendered content.
**Changes:**
- Added `send_telegram_structured()` in `notifications.py` and wired Event Alpha
  routed sends to use it directly. Legacy `send_telegram()` still returns a
  bool, while structured results now expose attempted/success, recipient counts,
  delivered/failed recipient counts, chunk counts, redacted error details, and a
  redacted channel summary.
- Extended `event_alpha_notification_delivery.py` and
  `event_alpha_notifications.py` with `partial_delivered`, stable
  `dedupe_key`/`dedupe_bucket` fields, heartbeat/day/status and digest/day
  dedupe buckets, old `content_hash` fallback, and
  `RSI_EVENT_ALPHA_NOTIFICATION_PARTIAL_MARKS_COOLDOWN` (default true).
  Partial delivery now marks cooldown by default so successful recipients do not
  get duplicate alerts, but can be made retryable with the config flag.
- Surfaced partial/blocked/would-send state through notification run summaries,
  delivery reports, the daily brief, artifact doctor, and the notification inbox.
  Partial-delivered alerts now get their own delivery-review queue.
- Expanded go/no-go output with provider health, provider reset when backoff is
  active, delivery report, and inbox commands. Updated `.env.example`,
  `Makefile`, `DECISIONS.md`, `ROADMAP.md`, and
  `research/EVENT_ALPHA_RUNBOOK.md` for the new delivery rules.
- Added regression tests for structured Telegram delivery, partial cooldown
  behavior, stable dedupe keys, partial inbox/reporting, and go/no-go commands.
**Verify:** `python3 tests/test_indicators.py` (400/400 passed);
`python3 -m compileall -q crypto_rsi_scanner tests`; `make event-llm-eval
PYTHON=python3`; `make event-llm-extract-eval PYTHON=python3`; `make
event-alpha-eval PYTHON=python3`; `make verify PYTHON=python3`; `make
event-alpha-notify-fixture-smoke PYTHON=python3`; `python3 main.py
--event-alpha-notification-deliveries-report --event-alpha-profile fixture
--event-alpha-artifact-namespace fixture_notify_smoke`; `python3 main.py
--event-alpha-notify-go-no-go --event-alpha-profile notify_no_key`.
**Notes/risks:** This stays research-only. No live trading, paper trades, normal
RSI signal writes, or LLM-created `TRIGGERED_FADE` were added; `TRIGGERED_FADE`
remains owned by `event_fade.py` + `proxy_fade`.

## 2026-06-20 — Polish Event Alpha notification delivery reliability · Codex
**Why:** Day-1 Event Alpha notification scheduling needed more reliable send
accounting before real unattended runs: boolean sends hid partial delivery, and
overlapping jobs could see a `sending` row but still attempt the same content.
**Changes:**
- Added `event_alpha_notification_sender.py` with
  `NotificationSendAttemptResult` and bool/structured result normalization.
  Existing Telegram sending stays compatible, but Event Alpha delivery rows can
  now record redacted recipient/chunk counts, partial failures, and channel
  summaries.
- Extended `event_alpha_notification_delivery.py` and
  `event_alpha_notifications.py` with `skipped_in_flight`, configurable
  `RSI_EVENT_ALPHA_NOTIFICATION_IN_FLIGHT_GRACE_MINUTES` (default 10), planned
  rows before sending, structured delivered/failed rows, stricter secret
  redaction, and cooldown marking only after full successful delivery. Partial
  delivery is recorded as failed metadata and remains retryable.
- Added `event_alpha_notification_go_no_go.py`,
  `main.py --event-alpha-notify-go-no-go`, and
  `make event-alpha-notify-go-no-go` to separate preview readiness from send
  readiness and summarize Telegram/send guard, locks, provider backoff, artifact
  writability, doctor status, cooldowns, and next command.
- Updated notification run, delivery, inbox, daily-brief, fixture-smoke, and
  runbook surfaces so delivered/failed/duplicate/in-flight/blocked/would-send
  states are distinct. The fixture smoke now writes a namespaced delivery
  ledger and reports `delivery_records_written`.
- Updated `ROADMAP.md`, `DECISIONS.md`, `.env.example`, and
  `research/EVENT_ALPHA_RUNBOOK.md`. Added regression tests for structured
  partial delivery, in-flight dedupe/retry, go/no-go output, and fixture
  delivery-ledger smoke coverage.
**Verify:** `python3 tests/test_indicators.py` passed 395/395.
`python3 -m compileall -q crypto_rsi_scanner tests` passed.
`make event-llm-eval PYTHON=python3` passed 9/9.
`make event-llm-extract-eval PYTHON=python3` passed 7/7.
`make event-alpha-eval PYTHON=python3` passed 11/11.
`make event-alpha-notify-fixture-smoke PYTHON=python3` wrote one delivered
fixture ledger row. `python3 main.py --event-alpha-notification-deliveries-report
--event-alpha-profile fixture --event-alpha-artifact-namespace
fixture_notify_smoke` reported delivered=1. `python3 main.py
--event-alpha-notify-go-no-go --event-alpha-profile notify_no_key` ran and
reported preview-ready/send-blocked state. `make verify PYTHON=python3` passed.
**Notes/risks:** Still research-only. No live trading, paper trades, normal RSI
signal writes, or LLM-created `TRIGGERED_FADE`. The structured Telegram wrapper
is best-effort around the existing boolean Telegram sender; it records
recipient/chunk intent and full-channel success/failure, not provider-native
per-chat acknowledgement details.

## 2026-06-20 — Harden notification run lock from Codex review · Claude
**Why:** Codex reviewed the run lock and flagged two P1s and a P3.
**Changes:**
- `event_alpha_run_lock.py`: made acquisition **atomic**. Replaced the
  read-then-write (TOCTOU race where two simultaneous starts could both acquire)
  with `os.open(O_CREAT|O_EXCL)` via `_create_lock_exclusive`. Stale takeover is
  also race-safe (`_steal_stale_lock` re-reads to confirm the same stale holder
  before unlinking, then a single exclusive recreate — exactly one concurrent
  recoverer wins; the loser re-reads and skips/degrades).
- `scanner.py`: the notify cycle now **always releases the lock on exceptions**.
  Split `event_alpha_notify_cycle` into a thin wrapper that runs the renamed
  `_event_alpha_notify_cycle_body` inside `try/finally`; the body stores the lock
  in a `lock_holder` dict right after acquiring, and the wrapper releases it in
  the finally, so an exception in card writing, sending, snapshot/ledger writes,
  or report formatting still releases the lock.
- `event_alpha_notifications.py`: the health heartbeat lane now uses the same
  delivery-ledger dedupe (`skip_as_duplicate`) and `record_sending` path as the
  digest/escalation lanes for idempotency consistency (P3).
**Verify:** `.venv/bin/python tests/test_indicators.py` passed 392/392 (added
`test_event_alpha_run_lock_acquisition_is_atomic` — exactly one of two
same-instant acquires wins — and `test_event_alpha_notify_cycle_releases_lock_on_exception`).
`make event-llm-eval`, `make event-llm-extract-eval`, `make event-alpha-eval`,
and `make verify` (all `PYTHON=.venv/bin/python`) passed. A live fixture notify
cycle ran end-to-end and left no lock file behind (released by the wrapper).
**Notes/risks:** Still research-only; no trading/paper/RSI rows or LLM-created
`TRIGGERED_FADE`. The atomic file lock is single-host best-effort (this
deployment is one Mac); cross-host coordination would need a shared lock service.

## 2026-06-20 — Add Event Alpha notification run lock + idempotent delivery ledger · Claude
**Why:** Scheduled/cron-style day-1 notification runs could overlap (a slow run
still finishing when the next fires) and double-send a research digest or race on
lane cooldown state. We want safe unattended operation while keeping everything
research-only.
**Changes:**
- Added `event_alpha_run_lock.py`: a best-effort, profile/namespace-scoped file
  lock (`<namespace>/event_alpha_notify.lock`) carrying run_id/profile/namespace/
  pid/acquired_at/command/hostname. Fresh lock → the next run skips safely and
  records a skipped notification run; stale lock (time or dead holder PID) → take
  over with `stale_notification_lock_recovered`; released on completion, and a
  crashed run is recovered by the next run (dead PID on host / stale window).
  Config: `RSI_EVENT_ALPHA_NOTIFY_LOCK_ENABLED` (1),
  `RSI_EVENT_ALPHA_NOTIFY_LOCK_STALE_MINUTES` (30),
  `RSI_EVENT_ALPHA_NOTIFY_ALLOW_OVERLAP` (0).
- Added `event_alpha_notification_delivery.py`: an append-only JSONL delivery
  ledger (`<namespace>/event_alpha_notification_deliveries.jsonl`) with
  planned/sending/delivered/failed/skipped_duplicate/blocked states and content-
  hash dedupe within a window. `event_alpha_notifications.send_notifications`
  now records each lane send and skips identical content already delivered;
  cooldown is only marked after a real delivery (never on dedupe-skip or failure).
  Records and channel summaries are redacted. Config:
  `RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT` (1),
  `RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_WINDOW_HOURS` (24),
  `RSI_EVENT_ALPHA_NOTIFICATION_DELIVERIES_PATH` (optional override).
- Hung the lock/delivery summary off Codex's notification-runs ledger:
  `notification_run_record` now carries lock_acquired/skipped_due_to_active_lock/
  stale_lock_recovered + delivery counts, surfaced in the notification-runs
  report, daily brief, and artifact doctor (which now warns on failed deliveries
  for the notification namespace). Lock/delivery fields flow via new
  `EventAlphaSendResult`/`EventAlphaPipelineResult` fields.
- Added `main.py --event-alpha-notification-deliveries-report` and
  `--event-alpha-notification-retry-failed` (dry-run scaffold; `--confirm`
  required; automated resend left as a documented TODO since the ledger stores
  redacted metadata only). New Make targets:
  `event-alpha-notify-no-key-scheduled` / `event-alpha-notify-llm-scheduled`
  (run lock + delivery ledger, real wall-clock time, fail-soft, exit 0 on
  partial provider failure), `event-alpha-notification-deliveries-report`, and
  `event-alpha-notification-retry-failed`.
- `TRIGGERED_FADE` still comes only from `event_fade.py` + `proxy_fade`; no
  trading, paper trades, normal RSI rows, or LLM-created triggers were added.
**Verify:** `.venv/bin/python tests/test_indicators.py` passed 390/390 (added 11
tests: lock acquire/skip/recover/release, fail-soft release, distinct profile
lock paths, disabled-lock fixture smoke, delivery dedupe/namespace isolation,
delivered+cooldown, failed-no-cooldown, dedupe-skips-send, blocked-when-disabled,
report grouping/redaction, scheduled-target invariants, run-summary→runs/doctor/
brief). `make event-llm-eval`, `make event-llm-extract-eval`,
`make event-alpha-eval`, and `make verify` (all `PYTHON=.venv/bin/python`)
passed. A live `--event-alpha-notify-cycle --event-alpha-profile notify_no_key`
ran end-to-end (network fail-soft, lock acquired/released, notification-runs row
shows the lock/delivery line); the deliveries report renders the namespaced
ledger.
**Notes/risks:** Built on top of Codex's existing notification-runs/inbox/
checklist work (re-applied fresh after a divergent remote, rather than a
conflicted merge). Scheduled targets still require `--event-alert-send` plus
`RSI_EVENT_ALERTS_ENABLED=1` and Telegram config to deliver. Retry-failed is a
dry-run scaffold only; re-run the scheduled cycle to resend.

## 2026-06-20 — Polish day-1 Event Alpha provider operations · Codex
**Why:** Day-1 notification burn-in needed an operator-safe way to inspect and
clear stale provider backoff, force one run without mutating health state, and
avoid misleading card coverage from `index.md`.
**Changes:**
- Added profile-scoped provider health report/reset commands and Make targets.
  Reset requires `--confirm`, supports key/service/role/all selectors, clears
  only `disabled_until` and `consecutive_failures`, and does not call providers
  or send alerts.
- Added `RSI_EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF`,
  `--ignore-provider-backoff`, and `IGNORE_BACKOFF=1` for one-shot notification
  force-runs. Forced successful attempts leave provider health unchanged; fresh
  failures are still recorded and the run/notification ledgers include
  `provider_backoff_ignored_for_run`.
- Fixed artifact doctor/burn-in card counting so actual research-card files are
  counted separately from `index.md`, and surfaced
  `research_card_files` / `research_card_index_present`.
- Added no-send `event-alpha-day1-start` / `event-alpha-day1-start-llm` flows
  and post-run notification next-step guidance for reports, inbox, daily brief,
  artifact doctor, provider health reset, and feedback.
- Updated `.env.example`, `DECISIONS.md`, `ROADMAP.md`, the Event Alpha runbook,
  Makefile help/targets, and regression tests.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed;
`python3 tests/test_indicators.py` passed 379/379; `make event-llm-eval
PYTHON=python3`, `make event-llm-extract-eval PYTHON=python3`, `make
event-alpha-eval PYTHON=python3`, and `make verify PYTHON=python3` passed.
Manual smokes passed: `make event-alpha-day1-start PYTHON=python3`, `make
event-alpha-notify-fixture-smoke PYTHON=python3`, `python3 main.py
--event-alpha-notify-cycle --event-alpha-profile notify_no_key`, and `python3
main.py --event-alpha-provider-health-report --event-alpha-profile
notify_no_key`. The live no-key notify smoke completed degraded/no-send with
expected public-provider GDELT/RSS warnings and printed provider reset/feedback
next steps.
**Notes/risks:** All paths remain research-only. No live trading, paper trades,
normal RSI signal writes, or LLM-created `TRIGGERED_FADE` were added.

## 2026-06-20 — Polish Day-1 Event Alpha notification operations · Codex
**Why:** Day-1 notification burn-in needed cleaner profile-scoped report
loading, a practical review inbox, and a safe local smoke path that does not
touch Telegram or live providers.
**Changes:**
- Made notification/run/alert/feedback reports profile/namespace-aware while
  preserving explicit path overrides, and expanded report context output to
  include notification, feedback, and research-card paths.
- Added `event_alpha_notification_inbox.py` plus
  `--event-alpha-notification-inbox` / `make event-alpha-notification-inbox`
  to list sent/would-send items missing feedback, unreviewed cards,
  heartbeat-only runs, and provider-degraded notification runs.
- Added `--event-alpha-notify-fixture-smoke` / `make
  event-alpha-notify-fixture-smoke`, which uses a deterministic fixture/test
  namespace and fake sender to write notification-run, alert snapshot, run
  ledger, and card artifacts without Telegram, live providers, trades, paper,
  or normal RSI routing.
- Improved notification-run summaries, daily brief fixed-clock warning lines,
  profile-aware feedback shortcuts, Makefile help/targets, `.env.example`,
  `DECISIONS.md`, `ROADMAP.md`, and the Event Alpha runbook.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed;
`python3 tests/test_indicators.py` passed 376/376; `make event-llm-eval
PYTHON=python3`, `make event-llm-extract-eval PYTHON=python3`, `make
event-alpha-eval PYTHON=python3`, and `make verify PYTHON=python3` passed.
Manual smokes passed: `python3 main.py --event-alpha-notify-cycle
--event-alpha-profile notify_no_key` completed in degraded no-send mode and
wrote notify_no_key run/notification rows; `python3 main.py
--event-alpha-notification-runs-report --event-alpha-profile notify_no_key`
loaded the namespaced report; `python3 main.py --event-alpha-notification-inbox
--event-alpha-profile notify_no_key` printed review queues; `make
event-alpha-notify-fixture-smoke PYTHON=python3` delivered one fake-sender
fixture notification and wrote fixture namespace artifacts.
**Notes/risks:** Public no-key providers returned expected degraded responses
including RSS 403 and GDELT 429/timeouts during the manual notify cycle. All
new paths remain research-only and cannot create `TRIGGERED_FADE`, send
Telegram without explicit send guards, trade, paper trade, or write normal RSI
signal rows.

## 2026-06-20 — Make Event Alpha notification clocks production-safe · Codex
**Why:** Day-1 notification/profile Make targets inherited the fixture research
clock by default, which could freeze live event windows and notification lane
cooldowns to June 15 unless an operator noticed.
**Changes:**
- Split `EVENT_FIXTURE_NOW` from blank-by-default `EVENT_RESEARCH_NOW` in the
  Makefile. Fixture targets explicitly use the fixture clock; profiled,
  burn-in, notification, and send targets only pass `RSI_EVENT_RESEARCH_NOW`
  when explicitly set.
- Added `event_clock_status` and fixed-clock notification send blocking, plus
  clock mode/age disclosure in status, preflight, notification preview,
  notification checklist, daily brief, and run-ledger rows.
- Normalized notification checklist preview-vs-send blockers so missing send
  guard/Telegram config is reported once, preview remains allowed, and actual
  sends are blocked for stale/future fixed clocks unless
  `RSI_EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY=1`.
- Updated `.env.example`, `AGENTS.md`, `DECISIONS.md`, `ROADMAP.md`, the Event
  Alpha runbook, and regression tests for Makefile dry-runs, clock status,
  fixed-clock blockers, cooldown date keys, and run-ledger clock metadata.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed;
`python3 tests/test_indicators.py` passed 373/373; `make event-llm-eval
PYTHON=python3`, `make event-llm-extract-eval PYTHON=python3`, `make
event-alpha-eval PYTHON=python3`, and `make verify PYTHON=python3` passed.
Manual smoke `python3 main.py --event-alpha-notify-cycle --event-alpha-profile
notify_no_key` ran without `RSI_EVENT_RESEARCH_NOW`, used the 2026-06-20 wall
clock, failed soft on public-provider 429/403 responses, wrote local research
artifacts, and did not send.
**Notes/risks:** Actual notification delivery is still guarded by
`--event-alert-send`, `RSI_EVENT_ALERTS_ENABLED=1`, Telegram config, and now
the stale/future fixed-clock guard. No live trading, paper trades, normal RSI
signal writes, or LLM-created `TRIGGERED_FADE` were added.

## 2026-06-20 — Fail-soft Event Alpha notification runtime failures · Codex
**Why:** `notify_no_key` could still crash or hang operationally when live
CoinGecko market enrichment or other expensive notification stages failed,
which defeats day-1 degraded heartbeat/run-ledger behavior.
**Changes:**
- Added fail-soft live market enrichment that returns empty rows with
  `market_enrichment_live_fetch_failed`, logs the error, and records
  `coingecko:market_enrichment` provider-health/backoff rows in notification
  mode while preserving non-fail-soft raising behavior.
- Wired notification discovery to continue anomaly/discovery work with empty
  market rows on live enrichment failures, and added provider-health backoff
  support for targeted `coingecko:watchlist_market` lookups.
- Added `NotificationRuntimeBudget`, explicit pipeline `cycle_completed` and
  `partial_results` flags, and a notification-only fail-soft wrapper that turns
  unexpected pipeline exceptions into `notification_cycle_failed_soft:
  <ErrorClass>` while still writing run and notification ledgers.
- Updated heartbeat, preview, checklist, notification-run report, and run-ledger
  summaries to show degraded/partial state, runtime-budget status, alertable
  counts, provider backoff, notification runtime/timeout/fail-fast settings,
  and preview-vs-send readiness.
- Updated `.env.example`, `DECISIONS.md`, `ROADMAP.md`, `Makefile`, and the
  Event Alpha runbook; added regression coverage for live CoinGecko fail-soft
  enrichment, discovery continuation, degraded heartbeat delivery, and
  notification-cycle exception handling.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed;
`python3 tests/test_indicators.py` passed 373/373; `make event-llm-eval
PYTHON=python3`, `make event-llm-extract-eval PYTHON=python3`, `make
event-alpha-eval PYTHON=python3`, and `make verify PYTHON=python3` passed.
Also ran `python3 main.py --event-alpha-notify-cycle --event-alpha-profile
notify_no_key`; it exited without traceback, marked `partial_results=true`,
and wrote run/notification summary artifacts with send disabled.
**Notes/risks:** Public no-key sources can still consume much of the 120s
notification budget when upstream endpoints time out or rate-limit. The cycle
now records degraded state and provider backoff instead of crashing, but actual
delivery remains guarded by `RSI_EVENT_ALERTS_ENABLED=1` plus Telegram config.
No live trading, paper trades, normal RSI signal writes, or LLM-created
`TRIGGERED_FADE` were added.

## 2026-06-19 — Harden Event Alpha day-1 notifications · Codex
**Why:** Day-1 Event Alpha notifications need to be usable immediately without
mixing profile cooldowns, hanging on public providers, or implying calibrated
research/trading trust.
**Changes:**
- Scoped notification cooldown/count/dedupe state by namespace/profile/global
  with legacy-key migration warnings, and made `notify_no_key`, `notify_llm`,
  and `research_send` use namespace-scoped state.
- Added notification runtime/timeout/fail-fast controls, RSS provider
  fail-fast behavior, and CoinGecko notification-mode retry/timeout limits so
  burn-in runs preserve partial results instead of blocking on slow sources.
- Added a day-1 notification checklist and notification-run summary artifact,
  report command, Make targets, and run-ledger notification summary fields.
- Split readiness into day-1 notification start, calibrated research send, and
  trading-out-of-scope states; updated routed/heartbeat copy to say
  `DAY-1 UNVALIDATED`, `Trading action: NONE`, and `Review before acting`.
- Updated `.env.example`, `DECISIONS.md`, `ROADMAP.md`, the Event Alpha
  runbook, and regression tests for scoped state, fail-fast behavior,
  readiness/checklist/reporting, message copy, and Make targets.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed;
`python3 tests/test_indicators.py` passed 369/369; `make event-llm-eval
PYTHON=python3`, `make event-llm-extract-eval PYTHON=python3`, `make
event-alpha-eval PYTHON=python3`, and `make verify PYTHON=python3` passed.
Also smoke-tested `make event-alpha-notify-no-key PYTHON=python3` with the send
guard disabled, `make event-alpha-notification-checklist PROFILE=notify_no_key
PYTHON=python3`, `make event-alpha-notification-runs-report PROFILE=notify_no_key
PYTHON=python3`, and `make -n event-alpha-notify-start-no-key PYTHON=python3`.
**Notes/risks:** Live no-key sources can still time out or 403, but notification
mode records provider backoff/fail-fast warnings and keeps sends guarded by
`RSI_EVENT_ALERTS_ENABLED=1` plus Telegram configuration. No live trading,
paper trades, normal RSI signal writes, or LLM-created `TRIGGERED_FADE` were
added.

## 2026-06-19 — Add Event Alpha day-1 notification burn-in · Codex
**Why:** The owner wants immediate Event Alpha research notifications from day
1 while keeping trading trust, paper trades, normal RSI rows, and calibrated
research-send promotion separate from unvalidated alerts.
**Changes:**
- Added `notify_no_key` and `notify_llm` profiles with isolated
`notification_burn_in` artifacts, router/watchlist/card auto-write defaults,
no-key public sources, and strict OpenAI budget caps for the LLM profile.
- Added `event_alpha_notifications.py` for lane-specific send state:
daily digest, instant escalation, deterministic triggered-fade dedupe, and
health heartbeat. Generic event-alert digest metadata remains separate.
- Added `main.py --event-alpha-notify-cycle`,
`--event-alpha-notify-preview`, and `--event-alpha-send-test`, plus Make
targets for notify no-key/LLM, preview, and test send.
- Updated routed Telegram copy to always label notifications as
`Research-only / unvalidated`, include `Not a trade signal`, stable
`alert_id`/`card_id`, lane/route/tier/playbook, event timing, market summary,
LLM role/confidence, research-card reference, and feedback command.
- Split readiness language into day-1 notifications, calibrated research send,
and trading-out-of-scope fields; documented startup in the runbook and env
sample.
- Added regression coverage for profiles, guard/preflight behavior, lane
cooldowns and triggered-fade dedupe, would-send accounting, message copy,
Make targets, and test-send refusal without the guard.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed;
`python3 tests/test_indicators.py` passed 366/366; `make event-llm-eval
PYTHON=python3`, `make event-llm-extract-eval PYTHON=python3`, and
`make event-alpha-eval PYTHON=python3` passed; `make
event-alpha-notify-preview PROFILE=notify_no_key PYTHON=python3` rendered a
no-send preview; `make verify PYTHON=python3` passed.
**Notes/risks:** Notification sends remain guarded by `--event-alert-send` plus
`RSI_EVENT_ALERTS_ENABLED=1` and Telegram config. `TRIGGERED_FADE` still comes
only from deterministic `event_fade.py` output on `proxy_fade`; LLM output
cannot create it.

## 2026-06-19 — Add Event Alpha profile preflight · Codex
**Why:** Event Alpha burn-in reports could still depend on manually injected
artifact paths, which made it possible for a profile command to inspect the
wrong namespace. Daily operation also needed an explicit preflight before
running profile-scoped cycles.
**Changes:**
- Added `event_alpha_preflight.py` and `main.py --event-alpha-preflight` to
  check profile existence, resolved artifact paths, provider readiness, LLM
  budget/key state, send guards, and writable namespaced artifact directories.
- Centralized report artifact resolution in `scanner.py` with
  `resolve_event_alpha_artifact_context_for_report(...)`, then wired burn-in,
  readiness, health, doctor, brief, missed, calibration, source reliability,
  tuning, burn-in-pack, explain, and card-writing paths through it.
- Updated daily briefs and report stdout to disclose profile, namespace,
  run mode, run ledger path, and alert store path.
- Made Makefile daily/burn-in/report targets profile-consistent and added
  `make event-alpha-preflight`.
- Documented the preflight/profile-path contract in `.env.example`,
  `ROADMAP.md`, `DECISIONS.md`, and `research/EVENT_ALPHA_RUNBOOK.md`.
**Verify:** `python3 tests/test_indicators.py` passed 361/361;
`make event-llm-eval PYTHON=python3`, `make event-llm-extract-eval
PYTHON=python3`, `make event-alpha-eval PYTHON=python3`, `python3 -m compileall
-q crypto_rsi_scanner tests`, and `make verify PYTHON=python3` passed.
`make event-alpha-preflight PROFILE=no_key_live PYTHON=python3` reported
`READY_TO_RUN: yes`. `make event-alpha-artifact-doctor PROFILE=no_key_live
STRICT=1 PYTHON=python3` ran and correctly reported `BLOCKED` because the
`no_key_live` namespace currently has no burn-in run rows.
**Notes/risks:** This is artifact/readiness plumbing only. It does not enable
sends, trade, paper trade, write normal RSI signals, alter tiers, or create
`TRIGGERED_FADE`.

## 2026-06-19 — Harden Event Alpha artifact consistency · Codex
**Why:** Event Alpha was ready for burn-in, but profile-specific reports still
needed stronger protection against legacy/default artifacts, missing
run-to-snapshot joins, and hidden external snapshot paths before daily
operation can be trusted.
**Changes:**
- Extended `event_alpha_artifacts.py` with explicit legacy-row filtering,
  snapshot availability classification, external-path detection, and safe path
  labels.
- Hardened `event_alpha_artifact_doctor.py` so alertable runs with claimed
  snapshot writes must join to matching alert rows in the inspected store;
  external snapshot paths, legacy rows, orphan alerts, mixed namespaces,
  missing provider health, and unknown feedback/outcome IDs are reported with
  strict-mode escalation where appropriate.
- Updated burn-in scorecards, checklists, v1 readiness, health guard, daily
  briefs, explain-last-run, and burn-in-pack export to ignore legacy/default
  artifacts by default and honor an explicit legacy include flag for migration
  review.
- Added CLI/Make/env controls for `--event-alpha-include-legacy-artifacts` and
  strict artifact doctor mode, plus runbook, roadmap, and decision updates.
- Expanded tests to cover snapshot lineage, legacy filtering, strict doctor
  behavior, fixture/test isolation, and profile-specific report warnings.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 360/360. `make event-llm-eval
PYTHON=python3`, `make event-llm-extract-eval PYTHON=python3`, and `make
event-alpha-eval PYTHON=python3` passed. `make event-alpha-artifact-doctor
PYTHON=python3 STRICT=1` ran successfully and correctly reported the empty
`no_key_live` burn-in namespace as `BLOCKED`. `make verify PYTHON=python3`
passed.
**Notes/risks:** This is artifact hygiene only. Legacy-included reports are for
migration review, not promotion evidence. No sends, paper trades, live signal
rows, normal RSI routing, execution, or `TRIGGERED_FADE` behavior changed.

## 2026-06-19 — Make Event Alpha artifacts burn-in-safe · Codex
**Why:** Event Alpha burn-in artifacts were still easy to mix across fixture,
test, replay, no-key, LLM, and research-send runs. That made readiness reports
and review packs vulnerable to false confidence or false blockers.
**Changes:**
- Added `event_alpha_artifacts.py` for profile/run-mode/namespace artifact
  context and operational filtering, plus `event_alpha_artifact_doctor.py` for
  local lineage/contamination diagnostics.
- Added run-mode, namespace, artifact-path, snapshot-write, and run-id lineage
  to Event Alpha pipeline results, run-ledger rows, and alert snapshots.
- Updated `scanner.py` so profiled Event Alpha cycles resolve namespaced
  artifact paths, block snapshot writes for `test`/`fixture`/`replay` run modes,
  and expose `--event-alpha-artifact-doctor`,
  `--event-alpha-artifact-namespace`, and
  `--event-alpha-include-test-artifacts`.
- Made burn-in scorecards, v1 readiness, health guard, and burn-in packs filter
  non-operational artifact rows by default; burn-in packs now include a manifest
  and artifact-doctor report, and research cards include artifact lineage.
- Updated Makefile profile artifact defaults/doctor target, `.env.example`,
  `ROADMAP.md`, and `DECISIONS.md`; added regression coverage in
  `tests/test_indicators.py`.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 360/360.
`make event-alpha-artifact-doctor PYTHON=python3` ran and correctly reported a
blocked no-row `no_key_live` namespace. `make event-llm-eval PYTHON=python3`,
`make event-llm-extract-eval PYTHON=python3`, `make event-alpha-eval
PYTHON=python3`, and `make verify PYTHON=python3` passed.
**Notes/risks:** This is artifact hygiene only. It does not enable sends, alter
tiers, write normal RSI signals, paper trade, execute, or create
`TRIGGERED_FADE`.

## 2026-06-19 — Add Event Alpha v1 operations gates · Codex
**Why:** Event Alpha burn-in needed a clear v1 operating surface: readiness
flags, freshness health checks, review-pack export, and weekly tuning
suggestions that can run daily without becoming alert or trading authority.
**Changes:**
- Added `event_alpha_v1_readiness.py`, `event_alpha_health_guard.py`,
  `event_alpha_tuning.py`, and `event_alpha_burn_in_pack.py` for pure
  artifact-based readiness, health, tuning, and clean zip export reports.
- Wired `--event-alpha-v1-readiness`, `--event-alpha-health-guard`,
  `--event-alpha-tuning-worksheet`, and
  `--event-alpha-export-burn-in-pack` through `scanner.py`, plus Make targets
  and `.env.example` health thresholds.
- Extended research cards with a lifecycle timeline covering watchlist
  timestamps, latest monitor context, feedback labels, and filled outcomes.
- Added disabled launchd/cron schedule examples under `research/` and updated
  `research/EVENT_ALPHA_RUNBOOK.md`.
- Ignored local burn-in pack zip artifacts so review exports are not committed.
- Added offline regression coverage in `tests/test_indicators.py`.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 359/359. Smoke-ran
`python3 main.py --event-alpha-v1-readiness --days 7`,
`python3 main.py --event-alpha-health-guard`,
`python3 main.py --event-alpha-tuning-worksheet`,
`python3 main.py --event-alpha-export-burn-in-pack
/tmp/event_alpha_burn_in_pack_smoke.zip`, and the matching Make wrappers.
`make event-llm-eval PYTHON=python3`, `make event-llm-extract-eval
PYTHON=python3`, `make event-alpha-eval PYTHON=python3`, and `make verify
PYTHON=python3` passed.
**Notes/risks:** These reports and packs are local research artifacts only.
They do not enable sends, alter alert tiers, apply priors, create
`TRIGGERED_FADE`, paper trade, write live signal rows, or execute.

## 2026-06-19 — Add Event Alpha burn-in readiness gates · Codex
**Why:** Event Alpha needed burn-in reports to line up with the requested
operational profile and to show whether required artifacts are actually present
before any research-send promotion.
**Changes:**
- Added profile-aware latest-run helpers in `event_alpha_run_ledger.py` and
  wired requested/selected/profile-match output into daily briefs and
  explain-last-run reports.
- Extended `event_alpha_burn_in.py` with artifact coverage metrics and added
  `event_alpha_burn_in_checklist.py`, `--event-alpha-burn-in-checklist`, and
  `make event-alpha-burn-in-checklist` for readiness blockers/warnings/next
  actions.
- Made provider-health wrappers accept deterministic `now` values while keeping
  legacy provider signatures working.
- Added candidate-level replay policy diffs with score/tier/route deltas plus
  optional feedback/outcome context.
- Added latest watchlist monitor context to research cards and exposed profile
  artifact-policy contracts in profile/status output.
- Updated `.env.example`, `ROADMAP.md`, `DECISIONS.md`, and
  `research/EVENT_ALPHA_RUNBOOK.md`; added regression coverage in
  `tests/test_indicators.py`.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 358/358. `make event-llm-eval
PYTHON=python3`, `make event-llm-extract-eval PYTHON=python3`,
`make event-alpha-eval PYTHON=python3`, and `make verify PYTHON=python3`
passed. `make event-alpha-burn-in-checklist PYTHON=python3` printed the
research-only checklist successfully.
**Notes/risks:** The checklist is a readiness report only. It does not enable
sends, alter thresholds, create `TRIGGERED_FADE`, paper trade, write live signal
rows, or execute.

## 2026-06-19 — Polish Event Alpha burn-in daily radar · Codex
**Why:** Event Alpha needed a coherent daily burn-in surface: profile-aware
reports, provider health by service/role, active watchlist enrichment hints,
policy comparison replay, stable alert/card IDs, and a compact scorecard for
recent run quality.
**Changes:**
- Added `event_watchlist_enrichment.py` and integrated derivative/supply
  enrichment hints into active watchlist monitoring without allowing monitor
  updates to create `TRIGGERED_FADE`.
- Added `event_alpha_burn_in.py` plus `--event-alpha-burn-in-scorecard`/`--days`
  and `make event-alpha-burn-in-scorecard` for local run/alert/feedback/missed/
  provider/LLM budget summaries.
- Extended profile-aware report paths in `scanner.py` for daily brief,
  explain-last-run, router report, card writing, replay comparison, and burn-in
  status, with latest-profile inference for daily briefs.
- Upgraded provider health rows to `provider_service:provider_role` keys while
  preserving legacy name-only backoff compatibility.
- Added stable routed `alert_id`/`card_id` values to router reports, Telegram
  digest copy, alert snapshots, feedback lookup, and research-card filenames.
- Expanded local replay comparison across baseline, priors, LLM advisory,
  router-threshold, and profile variants.
- Updated `.env.example`, `ROADMAP.md`, `DECISIONS.md`, and
  `research/EVENT_ALPHA_RUNBOOK.md`; added regression tests for the new
  operational paths.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 357/357. `make event-llm-eval
PYTHON=python3` passed 9/9 golden cases. `make event-llm-extract-eval
PYTHON=python3` passed 7/7 golden cases. `make event-alpha-eval
PYTHON=python3` passed 11/11 golden checks. `make verify PYTHON=python3`
passed. `make event-alpha-burn-in-scorecard PYTHON=python3` printed the local
7-day burn-in scorecard successfully.
**Notes/risks:** All new paths remain research-only. Derivatives/supply monitor
hints can only become router material-change reasons; they cannot create
`TRIGGERED_FADE`, normal RSI alerts, paper trades, live DB signal rows, or
execution.

## 2026-06-19 — Polish Event Alpha policy-comparable daily radar · Codex
**Why:** The Event Alpha Radar needed one more daily-operations pass so live
research sources, active watchlist monitoring, prior comparisons, replay, daily
briefs, and research cards behave like one auditable operating system rather
than separate reports.
**Changes:**
- Expanded `event_provider_health.py` with wrappers for catalyst search,
  event-source, universe, and derivatives providers; wired health/backoff into
  live GDELT/RSS/Polymarket/CryptoPanic discovery sources plus live CoinGecko
  universe and Coinalyze derivatives enrichment.
- Added provider warnings to `EventDiscoveryResult` so skipped/backoff provider
  rows flow into Event Alpha pipeline warnings and run-ledger rows.
- Extended `event_watchlist_market.py` with opt-in targeted CoinGecko
  watchlist lookup by active `coin_id`, max-asset limits, TTL cache hits, and
  fail-soft fallback to cycle/fixture rows.
- Expanded `event_alpha_replay.py` from artifact counting into a local replay
  harness that can reconstruct discovery alerts, optional fixture/cache LLM
  advisory, bounded priors, temporary watchlist refresh, router decisions, and
  before/after tier/score comparisons without live providers or sends.
- Added `--event-alpha-priors-shadow-report` and the matching Make target for
  in-memory prior comparison without writing snapshots.
- Upgraded daily brief sections with provider health, LLM budget, new-vs-last
  run, hotter watchlist rows, alertable decisions, cards, missed opportunities,
  calibration recommendations, suppression reasons, and why alerts were or were
  not sent.
- Added a trade-readiness checklist section to research cards, using
  playbook-specific review language for proxy fades, listings, unlocks, and
  market anomalies.
- Added burn-in/review Make workflows:
  `event-alpha-burn-in-no-key`, `event-alpha-burn-in-llm`, and
  `event-alpha-weekly-review`.
- Added offline regression tests for universal provider health wrappers,
  targeted watchlist market cache/fallback, raw replay, priors shadow, daily
  brief/card sections, and burn-in Make targets.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 355/355. `make event-llm-eval
PYTHON=python3` passed 9/9 golden cases. `make event-llm-extract-eval
PYTHON=python3` passed 7/7 golden cases. `make event-alpha-eval
PYTHON=python3` passed 11/11 golden checks. `make verify PYTHON=python3`
passed.
**Notes/risks:** The new live-provider protection and targeted watchlist market
refresh are still research-only and opt-in. Replay writes only temporary
watchlist state unless an explicit report path is added later. Priors shadow
does not apply priors or write artifacts. None of these paths can create
`TRIGGERED_FADE`, send normal RSI alerts, paper trade, write live signal rows,
or execute.

## 2026-06-19 — Polish Event Alpha daily-use operations · Codex
**Why:** Event Alpha had strong research reports, but daily use still needed
targeted active-watchlist market refresh, provider backoff state, opt-in
calibration-prior application, a daily brief, faster feedback labels, replay,
and safe artifact retention.
**Changes:**
- Extended `event_watchlist_market.py` with targeted fixture/CoinGecko-style
  market providers, source/cache metadata, and fail-soft fallback to cycle rows.
- Added `event_provider_health.py`, `event_alpha_priors.py`,
  `event_alpha_daily_brief.py`, `event_alpha_replay.py`, and
  `event_alpha_retention.py` for provider circuit breakers, bounded opt-in
  research priors, daily Markdown briefs, local artifact replay, and dry-run
  retention pruning.
- Wired priors/watchlist market TTL/provider health/status into
  `scanner.py`, `event_alpha_pipeline.py`, config, `.env.example`, and Make
  targets, including `event-alpha-daily-brief`, `event-alpha-replay`,
  `event-alpha-prune-artifacts`, and quick feedback targets.
- Added feedback unmatched-label support for shorthand review notes while
  preserving strict default `--event-feedback-mark` behavior.
- Updated `DECISIONS.md`, `ROADMAP.md`, and
  `research/EVENT_ALPHA_RUNBOOK.md` with the daily-use operating boundary.
- Added offline regression tests for targeted watchlist market lookup, provider
  backoff, priors audit fields, daily brief/replay/retention, and unmatched
  feedback artifacts.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner` passed.
`python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 351/351. `make event-llm-eval
PYTHON=python3` passed 9/9 golden cases. `make event-llm-extract-eval
PYTHON=python3` passed 7/7 golden cases. `make event-alpha-eval
PYTHON=python3` passed 11/11 golden checks. `make verify PYTHON=python3`
passed.
**Notes/risks:** Calibration priors are still off unless
`RSI_EVENT_ALPHA_APPLY_PRIORS=1`; they are bounded research-ranking adjustments
only. Replay and pruning use local artifacts only, and pruning is dry-run unless
`--confirm`/`CONFIRM=1` is supplied. None of these paths can create
`TRIGGERED_FADE`, trade, paper trade, write normal RSI signal rows, or execute.

## 2026-06-19 — Add Event Alpha self-improvement operations loop · Codex
**Why:** Event Alpha could run daily, but the operator loop still needed shared
identity semantics, better active-watchlist market refresh selection,
source/provider reliability reporting, reviewable calibration-prior exports,
proposed eval-case generation, card-file output, and a clear runbook.
**Changes:**
- Added `event_identity.py` and routed catalyst-search plus missed-opportunity
  identity checks through it, preserving URL/source-origin/common-word symbol
  rejection and resolver-validated LLM identity behavior.
- Added `event_watchlist_market.py` plus monitor market-source config so active
  watchlist monitoring can select fixture, cycle, or CoinGecko-style rows
  fail-soft without creating trigger authority.
- Added source reliability, calibration-prior export, proposed eval-case export,
  last-run explain, and research-card write/index artifact paths with CLI and
  Make targets.
- Updated Event Alpha profiles/status, `.env.example`, `ROADMAP.md`,
  `DECISIONS.md`, and added `research/EVENT_ALPHA_RUNBOOK.md`.
- Added regression tests for identity field safety, missed diagnostics,
  watchlist market source selection, reliability recommendations, priors export,
  proposed eval exports, research card writes, and last-run explanations.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 347/347. `make event-llm-eval
PYTHON=python3` passed 9/9 golden cases. `make event-llm-extract-eval
PYTHON=python3` passed 7/7 golden cases. `make event-alpha-eval
PYTHON=python3` passed 11/11 golden checks. `make verify PYTHON=python3`
passed. Smoke-ran `python3 main.py --event-alpha-explain-last-run` and
`python3 main.py --event-source-reliability-report`.
**Notes/risks:** All new outputs are research artifacts. Priors are exported
but not applied, proposed eval cases do not mutate canonical fixtures, and none
of these paths can create `TRIGGERED_FADE`, normal RSI alerts, paper trades,
live signal rows, or execution.

## 2026-06-18 — Polish Event Alpha daily operations · Codex
**Why:** Event Alpha had strong operational reports, but daily cycles still
needed profile RSS readiness fixes, active-watchlist monitor routing inside the
cycle, precise send accounting, safer missed-opportunity identity diagnostics,
cluster-aware research cards, and runbook Make targets.
**Changes:**
- Fixed live Event Alpha profiles that enable project-blog/RSS sources so they
  also load the default checked-in RSS URL list and show `project_blog_rss`
  ready in profile-aware status.
- Added opt-in watchlist monitor cycle integration with
  `RSI_EVENT_WATCHLIST_MONITOR_ENABLED`,
  `RSI_EVENT_WATCHLIST_MONITOR_MARKET_PATH`, and
  `RSI_EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES`; material monitor hints now flow
  through the existing router/cooldown lanes instead of creating separate
  alerts.
- Added structured Event Alpha send accounting for requested/attempted/success,
  attempted/delivered item counts, and block reasons, and persisted those fields
  in the run ledger.
- Hardened missed-opportunity diagnostics so URL-only and publisher/source
  metadata matches do not become `resolver_missed_asset`; title/body/event text
  or validated LLM quotes remain the strong evidence path.
- Made research cards cluster-aware when `event_graph` data is supplied, showing
  cluster confidence, source diversity, accepted links by kind, rejected/noise
  links, source origins, URLs, and warnings.
- Added operational Make targets: `event-alpha-daily-report`,
  `event-alpha-daily-llm-report`, `event-alpha-daily-send`,
  `event-alpha-health`, and `event-alpha-open-items`.
**Verify:** `python3 tests/test_indicators.py` passed 339/339. `make
event-llm-eval PYTHON=python3` passed 9/9 golden cases. `make
event-llm-extract-eval PYTHON=python3` passed 7/7 golden cases. `make
event-alpha-eval PYTHON=python3` passed 11/11 golden checks. `make verify
PYTHON=python3` passed.
**Notes/risks:** Still research-only. Monitor updates cannot create
`TRIGGERED_FADE`; the send path uses router-approved decisions only and remains
guarded by `RSI_EVENT_ALERTS_ENABLED=1` plus `research_only` mode.

## 2026-06-18 — Add Event Alpha operational radar reports · Codex
**Why:** Event Alpha had source discovery, LLM advisory, playbooks, watchlist
state, routing, and alert snapshots, but daily operation still needed a run
ledger, profile-aware status, active watchlist monitoring, missed-opportunity
review, calibration summaries, and rich per-alert cards.
**Changes:**
- Added `event_alpha_run_ledger.py` plus `--event-alpha-runs-report` and
  profile-aware `--event-alpha-status`, with run counts for sources, anomalies,
  catalyst search, LLM cache/budget use, watchlist/router output, sends, and
  warnings.
- Added `event_watchlist_monitor.py` so active RADAR/WATCHLIST/HIGH_PRIORITY/
  EVENT_PASSED/ARMED rows can be refreshed from market state without a new
  article/source row.
- Added `event_alpha_missed.py`, `event_alpha_calibration.py`, and
  `event_research_cards.py` for missed large-move diagnostics, feedback/outcome
  calibration recommendations, and Markdown review cards.
- Hardened catalyst-search identity evidence so URL-only and publisher/source
  origin matches are rejected with explicit reason codes while title/body/event
  text, contract-address URL paths, and quote/resolver-validated LLM extraction
  remain valid evidence.
- Added safer `full_llm_live` profile budget caps, `research_send` alertable
  snapshot retention, new Make targets, `.env.example` knobs, and regression
  tests.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 337/337. `make event-llm-eval
PYTHON=python3` passed 9/9 golden cases. `make event-llm-extract-eval
PYTHON=python3` passed 7/7 golden cases. `make event-alpha-eval
PYTHON=python3` passed 11/11 golden checks. `make verify PYTHON=python3`
passed.
**Notes/risks:** All new paths are local research artifacts/reports. They do
not write live signal/paper tables, route normal RSI alerts, execute orders, or
let LLM/search/watchlist monitoring create `TRIGGERED_FADE`.

## 2026-06-18 — Harden Event Alpha catalyst identity and routing · Codex
**Why:** The dynamic Event Alpha catalyst-search loop needed to avoid attaching
generic catalyst articles to hot tickers, reduce repeated provider fetches, make
LLM budgets durable across runs, and route material watchlist updates as clean
research alerts without changing trading boundaries.
**Changes:**
- Made catalyst-search queries identity-aware with coin/project aliases,
  contracts, pair formats, common-word symbol rejection, LLM extraction identity
  hints, and result reason codes such as `identity_missing_cap` and
  `common_word_identity_rejected`.
- Added per-run provider fetch/cache stats and broad-source caching so RSS and
  Polymarket fetch once per run while query-specific providers cache duplicate
  searches.
- Added persistent JSON LLM budget ledger tracking daily extractor/relationship
  calls, cache hits/misses, skipped rows, and estimated cost; wired runtime
  config and `.env.example`.
- Added cluster confidence/source/time/link-kind components to Event Alpha
  alerts, material-change watchlist markers, router lanes, per-run route caps,
  and triggered-fade routing before duplicate suppression.
- Added playbook-specific Event Alpha outcome metrics for volatility,
  up-then-fade, MFE/MAE ratio, benchmark underperformance hooks, timing, and
  anomaly→catalyst tracking.
- Updated `.env.example`, `ROADMAP.md`, `DECISIONS.md`, and regression tests.
**Verify:** `python3 tests/test_indicators.py` passed 333/333.
`make event-llm-eval PYTHON=python3` passed 9/9 golden cases. `make
event-llm-extract-eval PYTHON=python3` passed 7/7 golden cases. `make
event-alpha-eval PYTHON=python3` passed 11/11 golden checks. `make verify
PYTHON=python3` passed. `python3 -m compileall -q crypto_rsi_scanner tests`
passed.
**Notes/risks:** This remains research-only. Search hits, LLM outputs, cluster
boosts, and router lanes still cannot create normal RSI alerts, paper trades,
live signal rows, orders, or `TRIGGERED_FADE`; deterministic `event_fade.py`
plus `proxy_fade` remains the only triggered-fade path.

## 2026-06-18 — Operationalize Event Alpha catalyst search profiles · Codex
**Why:** The Event Alpha catalyst-search loop needed to move beyond fixture
attachment into live-source evidence adapters, explicit search quality gates,
anomaly lifecycle reporting, reusable operating profiles, and LLM call-budget
guardrails while remaining research-only.
**Changes:**
- Added dynamic catalyst-search adapters for GDELT, project RSS, CryptoPanic,
  and Polymarket on top of the existing provider parsers, plus comma-list
  provider composition through `RSI_EVENT_CATALYST_SEARCH_PROVIDERS`.
- Added query/result scoring, result rejection, live-source requirement support,
  and richer catalyst-search reports with accepted/rejected evidence and reason
  codes.
- Added `event_anomaly_state.py` and wired Event Alpha pipeline reports to show
  anomaly lifecycle states from detected → searched → found → validated →
  playbook assigned/escalated/expired.
- Added Event Alpha operational profiles (`fixture`, `no_key_live`,
  `no_key_llm`, `api_live`, `full_llm_live`, `research_send`) plus CLI/Make
  profile entry points.
- Added LLM per-run/day/cache-TTL budget fields; cache hits do not consume
  budget and exhausted budgets skip lower-priority rows fail-soft.
- Updated `.env.example`, `ROADMAP.md`, `DECISIONS.md`, and regression tests.
**Verify:** `python3 tests/test_indicators.py` passed 325/325.
`make event-llm-eval PYTHON=python3` passed 9/9 golden cases. `make
event-llm-extract-eval PYTHON=python3` passed 7/7 golden cases. `make
event-alpha-eval PYTHON=python3` passed 11/11 golden checks. `make verify
PYTHON=python3` passed. `python3 -m compileall -q crypto_rsi_scanner tests`
passed.
**Notes/risks:** Profiles and live-source adapters still only collect research
evidence and route through deterministic discovery/playbooks. They do not alter
normal RSI alerts, paper trades, live signal rows, or event-fade eligibility;
`TRIGGERED_FADE` still only comes from `event_fade.py`.

## 2026-06-18 — Add dynamic Event Alpha catalyst-search loop · Codex
**Why:** Event Alpha had offline anomaly and catalyst-search scaffolding, but
the operating cycle still needed a real anomaly → catalyst-search → discovery
loop, better LLM extraction budgeting, and graph/playbook fixes for non-proxy
event relationships.
**Changes:**
- Added LLM raw-event extraction priority scoring so limited extraction budgets
  prefer high-severity anomalies, fresh catalyst articles, explicit asset
  mentions, and external-catalyst keywords over recaps/source noise.
- Expanded `event_catalyst_search.py` with research-only provider/data models,
  a fixture provider, bounded anomaly/query/result limits, source-evidence
  attachment, and a local catalyst-search report formatter.
- Wired optional catalyst search into `event_alpha_pipeline.run_event_alpha_operating_cycle`
  before deterministic discovery, then composed it with optional LLM extraction.
- Added `main.py --event-catalyst-search-report`, `make
  event-catalyst-search-fixture-report`, `make event-alpha-cycle-search`, and
  `make event-alpha-cycle-search-llm`.
- Broadened event graph accepted link kinds to proxy/direct/supply/derivatives
  while keeping infrastructure from boosting cluster confirmation by default.
- Fixed playbook precedence so explicit external proxy events beat loose
  listing keywords, while real exchange/perp/unlock/TGE event types keep their
  direct playbooks.
- Updated `.env.example`, `ROADMAP.md`, `DECISIONS.md`, and regression tests.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 320/320. `make event-llm-eval
PYTHON=python3` passed 9/9 golden cases. `make event-llm-extract-eval
PYTHON=python3` passed 7/7 golden cases. `make event-alpha-eval
PYTHON=python3` passed 11/11 golden checks. `make
event-catalyst-search-fixture-report PYTHON=python3` ran with fixture provider,
6 generated queries, 0 fixture results, and no live calls. `make verify
PYTHON=python3` passed.
**Notes/risks:** Catalyst search remains research-only and fixture-backed unless
explicitly configured later. Search results are raw evidence only: they still
must pass deterministic resolver/classifier/playbook logic, and they cannot
create `TRIGGERED_FADE`.

## 2026-06-18 — Make Event Alpha tiering playbook-first · Codex
**Why:** Event Alpha had expanded into multiple research playbooks, but alert
tiering still leaned too heavily on the old generic proxy-opportunity score.
The radar needed playbook-specific tier decisions, safer cluster confidence,
configurable snapshot retention, and offline catalyst-search scaffolding for
market anomalies without promoting anything to trading.
**Changes:**
- Added `event_alerts.resolve_playbook_alert_tier` so deterministic playbook
  assessment drives research tiers while hard rejections still win and
  `TRIGGERED_FADE` remains restricted to `proxy_fade` rows with a
  `SHORT_TRIGGERED` signal from `event_fade.py`.
- Tightened playbook scoring/selection so direct listings, perp listings,
  unlocks, and undated proxy-attention rows route through their own evidence
  rules instead of generic proxy scoring; low classifier confidence remains a
  store-only guard.
- Expanded `event_graph.EventCluster` with source diversity, event-time
  consensus, accepted/rejected asset counts, cluster confidence, and warnings;
  cluster confirmation can help accepted assets but not source-noise rows.
- Added `RSI_EVENT_ALPHA_SNAPSHOT_POLICY` and sampled-control support to
  research-only alert snapshot writes, with optional router context fields.
- Added `event_catalyst_search.py` for offline market-anomaly search-query
  generation and supplied-evidence attachment; attached evidence still has to
  pass normal discovery, resolver, classifier, and playbook tiering.
- Updated `.env.example`, `ROADMAP.md`, `DECISIONS.md`, and regression tests.
**Verify:** `python3 tests/test_indicators.py` passed 316/316.
`make event-llm-eval PYTHON=python3` passed 9/9 golden cases.
`make event-llm-extract-eval PYTHON=python3` passed 7/7 golden cases.
`make event-alpha-eval PYTHON=python3` passed 11/11 golden checks.
`python3 -m compileall -q crypto_rsi_scanner tests` passed.
`make verify PYTHON=python3` passed 316/316 tests, alert render smoke,
fixture backtest smoke, and paper scoreboard.
**Notes/risks:** Event Alpha remains research-only. Snapshot policies only
filter local JSONL artifacts; catalyst-search scaffolding does not fetch live
data or create alertable candidates without validated source evidence.

## 2026-06-18 — Polish Event Alpha operational alert semantics · Codex
**Why:** The Event Alpha Radar had the core modules, but its operating loop
still behaved too much like disconnected reports: LLM extractor `shadow` mode
could mutate raw evidence, Event Alpha cycle sends used broad alert candidates
instead of router-approved escalations, and alert/watchlist analytics did not
separate deterministic rule playbooks from LLM-adjusted effective playbooks.
**Changes:**
- Changed `event_alpha_pipeline.run_event_alpha_operating_cycle` so extractor
  `shadow` mode analyzes only, `advisory` mode is the only mode that applies
  quote-validated extraction hints, and unsupported/off modes skip fail-soft.
- Changed `event-alpha-cycle --event-alert-send` to send only
  `router_result.alertable_decisions`; broad digest sends remain on
  `--event-alert-report --event-alert-send`.
- Added routed Telegram digest formatting for Event Alpha router decisions.
- Added rule/effective/LLM-adjusted playbook fields on event alerts and
  persisted effective playbook identity through watchlist, router, snapshots,
  and reports while preserving rule playbooks for audit.
- Added playbook-specific alert reason/verification text and outcome profiles
  (`expected_direction`, `primary_horizon`, `success_metric`) with alert-store
  primary-horizon return, direction-hit, and MFE/MAE cohorts.
- Updated `.env.example`, `ROADMAP.md`, and `DECISIONS.md`; updated regression
  tests for extractor mode semantics, route-based sends, effective playbooks,
  playbook copy, and outcome cohorts.
**Verify:** `python3 tests/test_indicators.py` passed 313/313.
`make event-llm-eval PYTHON=python3` passed 9/9 golden cases.
`make event-llm-extract-eval PYTHON=python3` passed 7/7 golden cases.
`make event-alpha-eval PYTHON=python3` passed 11/11 golden checks.
`make verify PYTHON=python3` passed 313/313 tests, alert render smoke,
fixture backtest smoke, and paper scoreboard. `python3 -m compileall -q
crypto_rsi_scanner tests` passed.
**Notes/risks:** Event Alpha remains research-only. LLM output can adjust
research alert tiers/playbook grouping only; it cannot create `TRIGGERED_FADE`,
paper trades, live signal writes, normal RSI routing, or execution.

## 2026-06-18 — Centralize Event Alpha cycle orchestration in pipeline module · Codex
**Why:** A completion audit against the Pro-model plan showed the CLI was doing
the unified cycle ordering while `event_alpha_pipeline.py` only handled the
post-discovery half. The plan explicitly asked the pipeline module to own the
research operating cycle.
**Changes:**
- Added `event_alpha_pipeline.run_event_alpha_operating_cycle`, which performs
  optional raw-event LLM extraction, enrichment, deterministic discovery loading,
  event-alert/playbook ranking, optional relationship advisory, watchlist
  refresh, router decisions, and optional research send callback ordering.
- Simplified `scanner.event_alpha_cycle` so it delegates the operating-cycle
  sequence into `event_alpha_pipeline.py`.
- Added the explicit `event_research_now_from_config()` helper named in the
  plan.
- Added regression tests proving the pipeline module applies raw extraction
  before deterministic discovery and that the named research-clock helper works.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 312/312. `make event-llm-eval
PYTHON=python3` passed 9/9 golden cases. `make event-llm-extract-eval
PYTHON=python3` passed 7/7 golden cases. `make event-alpha-eval
PYTHON=python3` passed 11/11 golden checks. `make verify PYTHON=python3`
passed 312/312 tests, alert render smoke, fixture backtest smoke, and paper
scoreboard.
**Notes/risks:** This keeps sends opt-in and research-only. LLM extraction still
only enriches resolver evidence; it cannot create `TRIGGERED_FADE`.

## 2026-06-18 — Finish Event Alpha Radar graph, playbook, and alert-store phases · Codex
**Why:** The Pro-model polish plan still had unfinished later phases: catalyst
graph identity, broader deterministic playbooks, and alert snapshot/outcome
artifacts. The radar needed those pieces before we could honestly call the
phase plan complete.
**Changes:**
- Added `event_graph.py` to cluster differently worded events by external
  asset, event type, and event-date bucket while preserving rejected/noise asset
  links for review.
- Updated watchlist keys/state to use catalyst cluster identity so repeated
  source variants escalate the same research candidate instead of fragmenting
  state.
- Expanded `event_playbooks.py` beyond generic buckets into listing, perp
  listing, unlock, airdrop/TGE, fan/sports, political meme, RWA pre-IPO,
  AI IPO, security/regulatory shock, and unknown market-anomaly playbooks.
- Added playbook hypothesis, verification, timing-window, and invalidation
  fields to event-alert reports and Telegram research digest text.
- Added `event_alpha_alert_store.py`, `--event-alpha-alerts-report`,
  `--event-alpha-fill-outcomes`, `make event-alpha-alerts-report`, and
  `make event-alpha-fill-outcomes` for research-only alert snapshots and
  1h/4h/24h/72h/7d plus MFE/MAE outcome filling from local price fixtures.
- Updated `.env.example`, `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md`.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 311/311. `make event-llm-eval
PYTHON=python3` passed 9/9 golden cases. `make event-llm-extract-eval
PYTHON=python3` passed 7/7 golden cases. `make event-alpha-eval
PYTHON=python3` passed 11/11 golden checks. Full `make verify PYTHON=python3`
passed after documentation updates.
**Notes/risks:** All new paths are artifact/report-only. Non-proxy/direct
playbooks can become research alerts, but cannot create `TRIGGERED_FADE`;
event-fade triggers still come only from `event_fade.py`.

## 2026-06-18 — Feed LLM extraction hints into Event Alpha resolution · Codex
**Why:** The Pro-model plan called out that relationship-only LLM analysis can
reject bad links but cannot find missed proxy assets if the deterministic
resolver never receives the asset evidence. The unified Event Alpha cycle now
uses quote-validated extraction output as resolver input while keeping
deterministic validation in charge.
**Changes:**
- Added an optional fail-soft raw-event transform hook to `event_discovery.run_manual_discovery`.
- Updated `event_alpha_cycle --with-llm` to run raw-event extraction before
  deterministic discovery resolution and append high-confidence extraction hints
  to raw evidence.
- Hardened `event_llm_extractor.enrich_raw_events_with_extractions` so hints are
  appended to structured event descriptions as well as raw bodies.
- Added Event Alpha cycle report visibility for `extraction_hints_applied`.
- Added regression tests proving LLM hints cannot create candidates without a
  deterministic asset universe match, and can recover a candidate when resolver
  validation succeeds.
- Updated `AGENTS.md`, `DECISIONS.md`, and `ROADMAP.md`.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 308/308. `make event-llm-eval
PYTHON=python3` passed 9/9 golden cases. `make event-llm-extract-eval
PYTHON=python3` passed 7/7 golden cases. `make event-alpha-eval
PYTHON=python3` passed 11/11 golden checks. `make event-alpha-cycle-llm
PYTHON=python3 EVENT_WATCHLIST_STATE_PATH=/tmp/event_alpha_cycle_llm_upstream_watchlist_test.jsonl`
printed a research-only cycle report with the new `extraction_hints_applied`
field. `make verify PYTHON=python3` passed 308/308 tests, alert render smoke,
fixture backtest smoke, and paper scoreboard.
**Notes/risks:** This remains research-only. Extraction hints do not create
alerts, paper trades, live DB rows, event-fade eligibility, or `TRIGGERED_FADE`
without deterministic resolver/classifier/event-fade validation.

## 2026-06-18 — Add unified Event Alpha cycle · Codex
**Why:** The Pro-model plan called for a coherent Event Alpha operating loop
after the deterministic research clock: discovery/anomaly inputs, optional LLM
metadata, alert ranking, watchlist state, and local router decisions should be
available through one research-only command.
**Changes:**
- Added `event_alpha_pipeline.py` with `EventAlphaPipelineResult`,
  `run_event_alpha_pipeline`, and a concise cycle report formatter.
- Added `main.py --event-alpha-cycle` with `--with-llm` and optional
  `--event-alert-send` support through the existing research digest guardrails.
- Added `make event-alpha-cycle`, `make event-alpha-cycle-llm`, and
  `make event-alpha-cycle-send` fixture-oriented targets using the deterministic
  event research clock.
- Added pipeline/scanner tests proving the cycle builds alerts, writes
  research-only watchlist state, computes local router decisions, and keeps
  market-anomaly rows store-only.
- Updated `AGENTS.md`, `DECISIONS.md`, and `ROADMAP.md`.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed. `make
event-alpha-cycle-llm PYTHON=python3
EVENT_WATCHLIST_STATE_PATH=/tmp/event_alpha_cycle_llm_watchlist_test.jsonl`
printed a research-only cycle with 2 raw anomaly events, 1 candidate, 1
watchlist row, and 1 store-only route. `python3 tests/test_indicators.py`
passed 306/306. `make event-llm-eval PYTHON=python3` passed 9/9 golden cases.
`make event-llm-extract-eval PYTHON=python3` passed 7/7 golden cases. `make
event-alpha-eval PYTHON=python3` passed 11/11 golden checks. `make verify
PYTHON=python3` passed 306/306 tests, alert render smoke, fixture backtest
smoke, and paper scoreboard.
**Notes/risks:** This is still research-only orchestration. It does not write
live signal/outcome/paper rows, route normal RSI alerts, open paper trades,
execute orders, or let LLM output create `TRIGGERED_FADE`. Upstream use of LLM
raw-extraction hints before resolver validation remains the next Pro-plan phase.

## 2026-06-18 — Add deterministic event research clock · Codex
**Why:** Pro-model review found that fixed June 2026 event fixtures can silently
drift out of lookback windows as wall-clock time moves forward. Event research
reports and fixture Make targets need a deterministic clock so tests/review
artifacts stay reproducible.
**Changes:**
- Added `event_clock.py` plus `RSI_EVENT_RESEARCH_NOW` and CLI `--event-now`
  support for event/research commands.
- Threaded the injected clock through event discovery, event alerts, event alpha
  radar, LLM shadow/extraction reports, watchlist refresh, cache refresh,
  Binance announcement listen, event-fade reports/exports, and review-bundle
  manifest generation.
- Pinned fixture-oriented Make targets to `EVENT_RESEARCH_NOW ?=
  2026-06-15T16:00:00Z` while leaving live/no-key source targets on real time
  unless explicitly overridden.
- Added clock parser/regression coverage and updated scanner fixture tests to
  pass the fixed research clock explicitly.
- Documented the env knob in `.env.example`, `ROADMAP.md`, and `DECISIONS.md`.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 304/304. `make event-llm-eval
PYTHON=python3` passed 9/9 golden cases. `make event-llm-extract-eval
PYTHON=python3` passed 7/7 golden cases. `make event-alpha-eval
PYTHON=python3` passed 11/11 golden checks. `make verify PYTHON=python3`
passed 304/304 tests, alert render smoke, fixture backtest smoke, and paper
scoreboard. `make event-discovery-report PYTHON=python3` printed the fixture
radar with the pinned `RSI_EVENT_RESEARCH_NOW=2026-06-15T16:00:00Z`.
**Notes/risks:** This is research-command determinism only. Normal RSI scans,
production cooldowns without `--event-now`, paper trading, and live execution
logic were not changed.

## 2026-06-18 — Sweep cleanup for warnings and config hygiene · Codex
**Why:** A codebase sweep found a recurring pandas `FutureWarning` in backtest
coverage plus a small safety issue where whitespace-padded falsey env values
could be interpreted as enabled. This pass keeps changes narrow and
verification-driven.
**Changes:**
- Updated `backtest._pct_true` to compute percentages with explicit float
  conversion and `mask`, removing the pandas downcast warning path.
- Made `_env_bool` strip whitespace before parsing, so values like `" 0 "` and
  `" false "` correctly disable opt-in flags.
- Added `test_env_bool_strips_whitespace`.
- Made package fixture/config/audit file I/O and touched test file I/O use
  explicit UTF-8 encodings.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 -W error::FutureWarning tests/test_indicators.py` passed 303/303,
confirming the pandas warning is gone. `python3 main.py --help` parsed
successfully. `make verify PYTHON=python3` passed 303/303 tests, alert render
smoke, fixture backtest smoke, and paper scoreboard. `pyflakes`/`ruff` were not
installed in this environment, so I used compile, tests, warning-as-error, CLI
help, grep, and a small AST sweep for bare `except`/mutable defaults instead.
**Notes/risks:** No strategy logic, routing, storage schema, or provider
behavior was changed.

## 2026-06-18 — Add Event Alpha feedback and eval artifacts · Codex
**Why:** The Event Alpha Radar needed a lightweight way to capture human
judgment on research rows (`useful`, `junk`, `watch`, `missed`, etc.) and a
small offline eval harness for route/feedback behavior, without converting
review labels into production signal logic.
**Changes:**
- Added `event_feedback.py` with append-only JSONL feedback records, allowed
  label validation, watchlist-row matching by key/event/symbol/coin, `missed`
  support for uncaptured opportunities, and report formatting.
- Added `event_alpha_eval.py` plus
  `fixtures/event_discovery/event_alpha_golden_cases.json` for offline
  route/feedback golden checks.
- Added `main.py --event-feedback-mark`, `main.py --event-feedback-report`,
  `make event-alpha-eval`, and `make event-feedback-report`.
- Added `RSI_EVENT_ALPHA_FEEDBACK_PATH` config/env support, scanner CLI tests,
  feedback artifact tests, and eval fixture tests.
- Updated `AGENTS.md`, `DECISIONS.md`, `ROADMAP.md`, `.env.example`, and
  `config.py` comments to record that Event Alpha feedback is review metadata
  only.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`make event-alpha-eval PYTHON=python3` passed 11/11 golden checks. `make
event-llm-extract-eval PYTHON=python3` passed 7/7 golden cases. `make
event-llm-eval PYTHON=python3` passed 9/9 golden cases. A temp CLI smoke ran
`make event-watchlist-refresh`, then `main.py --event-feedback-mark SOL
--event-feedback-label junk`, then `main.py --event-feedback-report`; it wrote
and read one `junk` feedback row without touching live storage. `python3
tests/test_indicators.py` passed 302/302. `make verify PYTHON=python3` passed
302/302 tests, alert render smoke, fixture backtest smoke, and paper scoreboard.
**Notes/risks:** Feedback labels do not mutate watchlist state, event-alert
tiers, event-fade eligibility, Telegram routing, live signal/outcome/paper
tables, paper trades, or execution. The Pro-model Event Alpha Radar design is
now implemented as a research-only local/eval system; the next work is operating
it and collecting reviewed evidence.

## 2026-06-18 — Add Event Alpha research router · Codex
**Why:** The Event Alpha watchlist now has persistent state and playbook labels,
but it needed a separate deterministic layer to decide which rows would be
stored, suppressed as duplicates, shown locally, or surfaced as research output
without promoting anything into Telegram, paper trading, live storage, or
execution.
**Changes:**
- Added `event_alpha_router.py` with artifact-only route decisions:
  `STORE_ONLY`, `SUPPRESS_DUPLICATE`, `LOCAL_REPORT`, `RESEARCH_DIGEST`,
  `HIGH_PRIORITY_RESEARCH`, and `TRIGGERED_FADE_RESEARCH`.
- Wired `main.py --event-alpha-router-report` and `make
  event-alpha-router-report` to route latest watchlist JSONL state only when
  `RSI_EVENT_ALPHA_ROUTER_ENABLED=1`.
- Added router safety tests for duplicate suppression, market-anomaly/source
  noise store-only behavior, proxy research routing, and the guard that a
  non-`proxy_fade` playbook cannot route a triggered-fade research decision.
- Updated `AGENTS.md`, `DECISIONS.md`, `ROADMAP.md`, `.env.example`, and
  `config.py` comments to record that router decisions remain local
  research/report metadata.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`make event-watchlist-refresh EVENT_WATCHLIST_STATE_PATH=/tmp/.../watchlist.jsonl
PYTHON=python3` plus `make event-alpha-router-report` routed the fixture SOL
market-anomaly row to `STORE_ONLY`. `make event-llm-extract-eval
PYTHON=python3` passed 7/7 golden cases. `make event-llm-eval PYTHON=python3`
passed 9/9 golden cases. `python3 tests/test_indicators.py` passed 300/300.
`make verify PYTHON=python3` passed 300/300 tests, alert render smoke, fixture
backtest smoke, and paper scoreboard.
**Notes/risks:** The router is not a send path. It cannot create
`TRIGGERED_FADE`, route normal RSI alerts, send Telegram, write live
signal/outcome/paper rows, open paper trades, or execute orders. Remaining
Event Alpha Radar work is lightweight feedback labels/evals.

## 2026-06-18 — Add Event Alpha playbook scoring · Codex
**Why:** Event Alpha candidates needed explicit research intent labels so
reports/watchlist state can distinguish proxy fades, proxy attention, direct
events, infrastructure/context, market anomalies, source-noise controls, and
ambiguous controls without treating all event alerts as the same kind of setup.
**Changes:**
- Added `event_playbooks.py` with deterministic playbook scoring, recommended
  research action, max tier metadata, and a `can_trigger_fade` safety flag.
- Wired playbook metadata into event-alert candidates, local/Telegram research
  formatting, and event-watchlist state rows.
- Added safety capping so a non-`proxy_fade` playbook cannot preserve a
  `TRIGGERED_FADE` tier even if an inconsistent candidate appears.
- Added regression tests for proxy fade, proxy attention, direct event,
  infrastructure/context, source-noise control, and market-anomaly playbooks.
- Updated `AGENTS.md`, `DECISIONS.md`, and `ROADMAP.md` to record that
  playbooks are deterministic research labels only.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 299/299. `make
event-alpha-no-key-report PYTHON=python3` printed the fixture SOL anomaly with
`playbook: market_anomaly`. `make event-watchlist-refresh` plus
`make event-watchlist-report` wrote/read one fixture SOL `RAW_EVIDENCE` row with
`playbook: market_anomaly` and zero alertable escalations. `make
event-llm-extract-eval PYTHON=python3` passed 7/7 golden cases. `make
event-llm-eval PYTHON=python3` passed 9/9 golden cases. `make verify
PYTHON=python3` passed 299/299 tests, alert render smoke, fixture backtest
smoke, and paper scoreboard.
**Notes/risks:** Playbooks cannot create `TRIGGERED_FADE`, route Telegram,
affect normal RSI alerts, write live signal/outcome/paper rows, open paper
trades, or execute orders. Remaining Event Alpha Radar phases are research
routing and feedback/evals.

## 2026-06-18 — Add Event Alpha watchlist state · Codex
**Why:** The Event Alpha Radar needs memory so repeated articles/anomalies do
not become repeated prompts, and so only meaningful state escalations are
surfaced for review. This adds a persistent research-only watchlist around
event-alert candidates without promoting alerts, paper trades, or execution.
**Changes:**
- Added `event_watchlist.py` with append-only JSONL state for
  `RAW_EVIDENCE`, `RADAR`, `WATCHLIST`, `HIGH_PRIORITY`, `EVENT_PASSED`,
  `ARMED`, `TRIGGERED_FADE`, `INVALIDATED`, and `EXPIRED`.
- Watchlist entries track first/last seen timestamps, source count, highest and
  latest score, latest tier, market/LLM context, alert history, duplicate
  suppression, and alertable-escalation metadata.
- Added `main.py --event-watchlist-refresh`, `main.py --event-watchlist-report`,
  `make event-watchlist-refresh`, and `make event-watchlist-report`.
- Added disabled-by-default watchlist config/path env vars and documented the
  artifact-only boundary in `AGENTS.md`, `DECISIONS.md`, and `ROADMAP.md`.
- Added tests for escalation tracking, duplicate suppression, expiration,
  backward-compatible watchlist reads, scanner wiring, and Makefile targets.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 298/298. `make
event-watchlist-refresh EVENT_WATCHLIST_STATE_PATH=/tmp/.../watchlist.jsonl
PYTHON=python3` plus `make event-watchlist-report` wrote/read one fixture SOL
`RAW_EVIDENCE` row with zero alertable escalations. `make
event-llm-extract-eval PYTHON=python3` passed 7/7 golden cases. `make
event-llm-eval PYTHON=python3` passed 9/9 golden cases. `make verify
PYTHON=python3` passed 298/298 tests, alert render smoke, fixture backtest
smoke, and paper scoreboard.
**Notes/risks:** The watchlist is state memory only. It cannot create
`TRIGGERED_FADE`, route Telegram research digests, affect normal RSI alerts,
write live signal/outcome/paper rows, open paper trades, or execute orders.
Remaining Event Alpha Radar phases are playbook scoring, research routing, and
feedback/evals.

## 2026-06-18 — Add market enrichment and anomaly radar phase · Codex
**Why:** The Event Alpha Radar needs market confirmation and anomaly-first
discovery without turning hot coins into event-fade candidates. This implements
the next research-only phase after raw-event extraction: market snapshots can
enrich candidates, and anomaly rows can point review toward possible catalysts
while remaining low-authority evidence.
**Changes:**
- Added `event_market_enrichment.py` to convert CoinGecko-style market rows into
  candidate market snapshots with return windows, volume, market cap, FDV,
  volume z-score, and distance-from-MA fields.
- Added `event_anomaly_scanner.py` to create research-only raw events from top
  movers, volume/mcap spikes, or volume z-score spikes; anomalies without
  catalyst evidence stay store-only and cannot trigger event fade.
- Wired market enrichment and anomaly discovery through event discovery,
  `main.py --event-alpha-radar-report`, and `make event-alpha-no-key-report`.
- Added disabled-by-default anomaly thresholds in config/`.env.example`,
  updated `AGENTS.md`, `DECISIONS.md`, and `ROADMAP.md`, and added regression
  coverage for enrichment precedence, anomaly safety, and scanner report output.
**Verify:** `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`python3 tests/test_indicators.py` passed 295/295. `make
event-alpha-no-key-report PYTHON=python3` printed one fixture SOL
market-anomaly row as `STORE_ONLY` with proxy/classifier rejection reasons.
`make event-llm-extract-eval PYTHON=python3` passed 7/7 golden cases. `make
event-llm-eval PYTHON=python3` passed 9/9 golden cases. `make verify
PYTHON=python3` passed 295/295 tests, alert render smoke, fixture backtest
smoke, and paper scoreboard.
**Notes/risks:** Market anomaly discovery is not a trading or event-fade
eligibility path. The remaining Event Alpha Radar phases are persistent
watchlist state, playbook scoring, research routing, and feedback/evals.

## 2026-06-18 — Add LLM raw-event extraction phase · Codex
**Why:** The downstream LLM advisory analyzer can reject bad event/asset links,
but it cannot recover asset mentions the deterministic resolver never surfaces.
This adds the first Event Alpha Radar phase: quote-validated raw-event
extraction that proposes catalysts, asset mentions, source-noise terms, and
date hints while keeping deterministic resolver/classifier gates authoritative.
**Changes:**
- Added frozen raw-extraction models, a quote-validating extractor, fixture and
  optional OpenAI extraction providers, cache-key metadata, and a research-only
  raw-event enrichment helper whose output still requires resolver validation.
- Added `main.py --event-llm-extract-report` and
  `make event-llm-extract-eval` with a golden fixture covering proxy assets,
  source noise, word collisions, infrastructure mentions, fan-token context,
  and invalid quote confidence clamping.
- Added disabled-by-default extractor config plus placeholder disabled flags for
  later Event Alpha Radar phases: market enrichment, anomaly scanner,
  watchlist, and router.
- Updated `.env.example`, `AGENTS.md`, `DECISIONS.md`, `ROADMAP.md`, and tests
  for the extractor boundary.
**Verify:** `make event-llm-extract-eval PYTHON=python3` passed 7/7 golden cases
with the expected invalid-quote clamp warning. `make event-llm-eval
PYTHON=python3` passed 9/9 relationship cases. `python3 -m compileall -q
crypto_rsi_scanner tests` passed. `python3 tests/test_indicators.py` passed
290/290. `make verify PYTHON=python3` passed 290/290 tests, alert render smoke,
fixture backtest smoke, and paper scoreboard.
**Notes/risks:** Extraction is shadow/research-only. It cannot create
`TRIGGERED_FADE`, event-alert tiers, normal RSI alerts, live DB rows, paper
trades, or orders; extracted assets are only resolver hints until deterministic
validation succeeds. Market enrichment, anomaly scanning, persistent watchlist
state, playbooks, and feedback remain later phases.

## 2026-06-18 — Add LLM advisory mode for event research alerts · Codex
**Why:** The LLM relationship analyzer could diagnose source-noise and
ticker-collision false positives, but event research alerts still used only the
deterministic rule tier. Advisory mode lets validated LLM output improve
research-alert quality without touching trade or event-fade eligibility logic.
**Changes:**
- Added copy-based LLM advisory tier adjustment for discovery-fed event research
  alerts, including LLM metadata fields and before/after report formatting.
- Wired `main.py --event-alert-report --with-llm` and
  `--event-alert-send --with-llm`; advisory changes apply only when
  `RSI_EVENT_LLM_MODE=advisory`.
- Hardened LLM cache keys with provider/model/prompt/schema/packet metadata.
- Added no-key event-alert Make targets and documented event alert / LLM env
  vars in `.env.example`.
- Updated `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and tests for the
  research-only advisory boundary.
**Verify:** Targeted advisory tests passed. `python3 tests/test_indicators.py`
passed 283/283. `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`make event-llm-eval PYTHON=python3` passed 9/9 golden cases with the expected
invalid-quote clamp warning. `make verify PYTHON=python3` passed 283/283 tests,
alert render smoke, fixture backtest smoke, and paper scoreboard.
**Notes/risks:** LLM advisory cannot create `TRIGGERED_FADE`, change
`event_fade.py` eligibility, route normal RSI alerts, write live
signal/outcome/paper rows, open paper trades, or imply execution.

## 2026-06-18 — Make LLM golden eval fail on drift · Codex
**Why:** `make event-llm-eval` printed the shadow report, but it did not fail if
golden LLM relationship roles/actions drifted. The eval should be a real
offline regression gate before the analyzer is used for review QA.
**Changes:**
- Added `crypto_rsi_scanner/event_llm_eval.py` to run the fixture discovery
  pipeline, fixture LLM provider, quote-validating analyzer, and expected
  role/relationship/action comparisons.
- Changed `make event-llm-eval` to call the evaluator directly and exit nonzero
  on mismatches.
- Added an explicit `max_confidence` expectation for the invalid-quote fixture
  so quote-validation/clamping regressions fail the eval.
- Updated `AGENTS.md`, `ROADMAP.md`, and tests for the stricter eval behavior.
**Verify:** Targeted eval tests passed. `make event-llm-eval PYTHON=python3`
passed 9/9 golden cases with the expected invalid-quote clamp warning. `python3
tests/test_indicators.py` passed 278/278. `python3 -m compileall -q
crypto_rsi_scanner tests` passed. `make verify PYTHON=python3` passed 278/278
tests, alert render smoke, fixture backtest smoke, and paper scoreboard.
**Notes/risks:** This still does not let LLM output affect event-alert tiers,
event-fade eligibility, paper trades, live DB rows, or notification routing.

## 2026-06-17 — Add LLM shadow relationship analyzer · Codex
**Why:** Event-discovery alerts need a research-only way to compare deterministic
proxy/direct rules against structured LLM relationship analysis without letting
the LLM influence trades, paper trades, normal alerts, or event-fade hard gates.
**Changes:**
- Added frozen LLM analysis models, a quote-verifying shadow analyzer, fixture
  and optional OpenAI Responses API providers, and disabled-by-default runtime
  config.
- Added `main.py --event-llm-shadow-report` and `make event-llm-eval` for
  offline fixture comparisons of rule role/relationship/tier vs LLM
  role/relationship/action.
- Added `fixtures/event_discovery/llm_golden_cases.json` with source-noise,
  ticker-collision, infrastructure, proxy, direct-beneficiary, and invalid-quote
  cases.
- Kept all LLM output advisory only: no alert-tier mutation, Telegram routing,
  paper trades, live DB writes, or event-fade eligibility changes.
- Updated `AGENTS.md`, `ROADMAP.md`, and standalone tests for the new shadow
  surface.
**Verify:** Targeted LLM regression tests passed. `make event-llm-eval
PYTHON=python3` passed. `python3 tests/test_indicators.py` passed 277/277.
`python3 -m compileall -q crypto_rsi_scanner tests` passed. `make verify
PYTHON=python3` passed 277/277 tests, alert render smoke, fixture backtest
smoke, and paper scoreboard.
**Notes/risks:** OpenAI live use requires explicit `RSI_EVENT_LLM_PROVIDER=openai`
and `RSI_EVENT_LLM_ENABLED=1`; missing keys fail soft. Fixture mode remains the
default and is suitable for offline tests/evals.

## 2026-06-17 — Tighten event-alert false-positive guards · Codex
**Why:** The Pro review found a few remaining research-alert false-positive
paths: publisher names repeated in snippets, `external_asset` being too broad
for proxy-event asset matching, and rejection gates not dominating inconsistent
triggered signals.
**Changes:**
- Hardened `event_resolver.py` so publisher suffix stripping applies to
  descriptions/snippets and `external_asset` is used as asset identity evidence
  only for direct event types.
- Expanded publisher/source noise terms for crypto/news sources seen in review
  rows.
- Adjusted `event_alerts.py` so rejection gates win before `SHORT_TRIGGERED`
  tiering, while proxy venues no longer suppress other rejection reasons.
- Expanded infrastructure classification for oracle/provider language so
  Chainlink-style World Cup oracle articles demote to `proxy_context`.
- Added regression tests for Bitcoin publisher-snippet noise,
  external-asset-only proxy false positives, proxy-venue low-confidence
  rejection, inconsistent triggered/direct candidate rejection, and Chainlink
  oracle infrastructure demotion.
**Verify:** Targeted regression tests passed. `python3 tests/test_indicators.py`
passed 270/270. `python3 -m compileall -q crypto_rsi_scanner tests` passed.
`make verify PYTHON=python3` passed 270/270 tests, alert render smoke, fixture
backtest smoke, and paper scoreboard.
**Notes/risks:** Event alerts remain research prompts only: no normal RSI
signal routing, paper trades, live signal DB rows, or execution.

## 2026-06-17 — Add event research alert ranking · Codex
**Why:** The event-discovery pipeline had validation/export tooling, but no
separate way to surface manageable research candidates without treating them as
trade signals. The Pro review also flagged publisher/source and common-word
resolver false positives that could create noisy candidates.
**Changes:**
- Added `crypto_rsi_scanner/event_alerts.py` with pure opportunity scoring,
  store/radar/watchlist/high-priority/triggered-fade tiers, report formatting,
  and research-only Telegram digest text.
- Added `main.py --event-alert-report` plus explicit opt-in
  `--event-alert-send`, gated by `RSI_EVENT_ALERTS_ENABLED=1` and separate
  event-alert cooldown/count metadata.
- Hardened `event_resolver.py` and `event_classification.py` against publisher
  suffixes, source-origin-only matches, common-word/ticker collisions, and
  market recap confidence inflation.
- Added disabled-by-default event-alert config knobs in `config.py`.
- Updated `AGENTS.md`, `ROADMAP.md`, `main.py` usage text, and `.gitignore`
  for the new research-alert surface and local source-copy artifact.
- Added offline tests for BTC/Bitcoin World, KuCoin source-origin, USA/ripple/
  HYPE/BEAT/PRIME false positives, market recap penalties, watchlist/radar/
  proxy-venue/triggered-fade alert tiers, and scanner report wiring.
**Verify:** `python3 tests/test_indicators.py` passed 269/269. `make verify
PYTHON=python3` passed 269/269 tests, alert render smoke, backtest fixture
smoke, and paper scoreboard. Manual fixture command
`RSI_EVENT_DISCOVERY_EVENTS_PATH=fixtures/event_discovery/raw_events.json
RSI_EVENT_DISCOVERY_ALIASES_PATH=fixtures/event_discovery/asset_aliases.json
RSI_EVENT_DISCOVERY_LOOKBACK_HOURS=120 RSI_EVENT_DISCOVERY_HORIZON_DAYS=2
python3 main.py --event-alert-report` printed the research-only ranked report.
**Notes/risks:** Event alerts are investigation prompts only. They do not
depend on human labels, do not route as normal RSI alerts, do not open paper
trades, do not write live signal rows, and do not promote event fade beyond
research.

## 2026-06-17 — Recheck live paper maturity · Codex
**Why:** The Pro-plan live evidence blockers depend on paper trades and outcome
cohorts maturing. A fresh refresh could have closed more open paper trades since
the previous status pass.
**Changes:**
- Ran `main.py --status`, `main.py --score --cohorts`, `main.py --report`, and
  `main.py --refresh-paper`.
- Updated `ROADMAP.md` to record that the follow-up paper refresh fetched all
  12 open histories and closed 0 trades.
**Verify:** `main.py --refresh-paper` completed: fetched 12/12 histories, closed
0 trades, paper book remains 11 closed / 12 open. `make verify` passed with
262/262 tests, alert render smoke, fixture backtest smoke, and paper scoreboard.
**Notes/risks:** Status/docs only. No live logic, registry priors, state rules,
event-fade labels, alerts, DB schema, or paper-trading rules changed.

## 2026-06-17 — Document review-bundle wrappers in agent rules · Codex
**Why:** The new bundle-oriented review Make targets should be the shared
default for Claude and Codex after a human labels the event-fade sidecar.
`AGENTS.md` still pointed mostly at lower-level raw CLI commands.
**Changes:**
- Updated `AGENTS.md` reports/open-next-steps sections to mention
  `event-fade-check-review-bundle`, `event-fade-apply-review-bundle`,
  `event-fade-review-applied-bundle`, and
  `event-fade-fill-review-bundle-outcomes`.
**Verify:** `make verify` passed with 262/262 tests, alert render smoke, fixture
backtest smoke, and paper scoreboard.
**Notes/risks:** Documentation/protocol only. No labels, alerts, live DB writes,
paper trades, or promotion changed.

## 2026-06-17 — Add review-bundle outcome wrapper · Codex
**Why:** The reviewed-bundle workflow still had one long manual command for
filling outcomes after reviewed trigger rows exist. A bundle-level Make target
keeps the post-label workflow consistent.
**Changes:**
- Added `event-fade-fill-review-bundle-outcomes`, driven by
  `EVENT_FADE_REVIEW_BUNDLE_DIR`, to fill outcomes from a bundle's applied
  sample and bundle-local `outcome_prices.json`.
- Updated the event-fade review quickstart to use the new target.
- Added Makefile dry-run coverage for the new wrapper.
**Verify:** `make -n event-fade-fill-review-bundle-outcomes` expands to the
expected latest-bundle fill command. `make verify` passed with 262/262 tests,
alert render smoke, fixture backtest smoke, and paper scoreboard.
**Notes/risks:** Workflow-only. This does not infer labels, create outcomes
without reviewed trigger rows, route alerts, write live DB rows, paper trade, or
promote event fade.

## 2026-06-17 — Add review-bundle Make wrappers · Codex
**Why:** After a human labels the event-fade sidecar, the next commands should
be hard to mistype. The existing Make targets required passing three separate
sample/template/output paths.
**Changes:**
- Added `event-fade-check-review-bundle`, `event-fade-apply-review-bundle`, and
  `event-fade-review-applied-bundle` targets driven by
  `EVENT_FADE_REVIEW_BUNDLE_DIR`.
- Updated the event-fade review quickstart to use the new bundle-oriented
  targets.
- Added Makefile regression coverage for the new dry-run path expansion.
**Verify:** `make -n event-fade-check-review-bundle` expands to the expected
latest-bundle check command. `make verify` passed with 262/262 tests, alert
render smoke, fixture backtest smoke, and paper scoreboard.
**Notes/risks:** Workflow-only. No labels were inferred or applied; event fade
remains research-only with no alerts, live DB writes, paper trades, or
promotion.

## 2026-06-17 — Add event-fade review quickstart · Codex
**Why:** The Pro-plan blocker is now human labeling. The latest `/tmp` bundle has
instructions, but a checked-in quickstart makes the handoff durable and gives
future agents exact commands for applying reviewed labels.
**Changes:**
- Added `research/EVENT_FADE_REVIEW_QUICKSTART_2026-06-17.md` with the latest
  bundle path, fields to fill, label rules, post-edit commands, and promotion
  guardrail.
**Verify:** `make verify` passed with 262/262 tests, alert render smoke, fixture
backtest smoke, and paper scoreboard.
**Notes/risks:** No labels were inferred or applied. Event fade remains
research-only with no alerts, live DB writes, paper trades, or promotion.

## 2026-06-17 — Add Pro-plan completion audit · Codex
**Why:** The remaining event-fade work kept converging on the same human-review
blocker. A checked-in requirement audit makes clear which parts of the Pro plan
are implemented and which parts still need human labels/live data.
**Changes:**
- Added `research/PRO_PLAN_COMPLETION_AUDIT_2026-06-17.md` with a
  requirement-by-requirement status table, latest bundle counts, remaining
  human-review steps, and promotion blockers.
**Verify:** `make verify` passed with 262/262 tests, alert render smoke, fixture
backtest smoke, and paper scoreboard.
**Notes/risks:** No code, signal logic, alerts, live DB writes, paper trades, or
promotion changed.

## 2026-06-17 — Refresh no-key event-fade review bundle · Codex
**Why:** The Pro-model plan now depends on building a reviewed event-fade
validation sample, so the shared roadmap should point at the freshest no-key
research bundle rather than stale local output.
**Changes:**
- Ran `make event-fade-no-key-review-cycle` into a fresh `/tmp` cache/bundle path
  with outcome-price export enabled.
- Updated `ROADMAP.md` with the new bundle path, counts, and GDELT rate-limit
  diagnostic.
**Verify:** The refresh wrote
  `/tmp/event_fade_no_key_review_bundle_20260617_continue` with 120 validation
  rows, 24 proxy candidates, 20 proxy-context controls, 8 direct rows, 68
  ambiguous rows, 116 missing machine event times, 0 eligible rows, and 0
  triggers. The balanced sidecar has 74 rows and `--event-fade-check-review-template`
  correctly reports it is not ready to apply because no human review fields have
  been filled yet. `make verify` passed with 262/262 tests, alert render smoke,
  fixture backtest smoke, and paper scoreboard.
**Notes/risks:** Research artifact/status only. No alerts, live DB writes, paper
trades, routing, or promotion. Human review remains the blocker before outcome
filling or any event-fade promotion.

## 2026-06-17 — Keep clean source export out of git status · Codex
**Why:** Running `make export-src` correctly creates a tracked-source-only zip
for external review, but the generated archive was left as an untracked file in
`git status`.
**Changes:**
- Added `crypto-rsi-scanner-source.zip` to `.gitignore` while leaving the
  existing `.gitattributes` export-ignore rule in place.
- Ran the event-fade review-template preflight on the latest no-key bundle; it
  correctly reports the untouched balanced sidecar is not ready to apply because
  it has no human review fields yet.
- Ran event-discovery status/runs checks to confirm no always-on configured
  event sources are currently ready and the latest cache metadata is readable.
**Verify:** `make export-src` wrote `crypto-rsi-scanner-source.zip`; archive
inspection found no `.env`, `.venv`, DB, log, backup, pycache, pytest-cache, or
event-fade-cache paths. `make verify` passed with 262/262 tests, alert render
smoke, fixture backtest smoke, and paper scoreboard.
**Notes/risks:** Process/docs only. The event-fade validation blocker remains
human labeling of `/tmp/event_fade_no_key_review_bundle_20260617_external_assets`.

## 2026-06-17 — Refresh live paper and outcome status · Codex
**Why:** Several roadmap items were waiting on live paper/outcome evidence. The
current local DB had more matured paper trades available, so the waiting status
needed a fresh evidence check.
**Changes:**
- Ran `main.py --refresh-paper`, which fetched 16/16 open histories and closed
  4 more paper trades.
- Checked `main.py --score --cohorts`, `main.py --report`, and `main.py --status`.
- Updated `ROADMAP.md` with the current paper, conviction-bucket, and state-cohort
  sample sizes while keeping those items waiting.
**Verify:** `main.py --refresh-paper` completed; paper book is now 11 closed /
12 open. `main.py --report` shows 102 matured 7d observations, with conviction
buckets low 8 / med 81 / high 13. `main.py --status` reports health OK.
`make verify` passed with 262/262 tests, alert render smoke, fixture backtest
smoke, and paper scoreboard.
**Notes/risks:** Docs/status only. No signal logic, registry priors, routing, or
state-conditioned live rules changed; samples remain too small for promotion.

## 2026-06-17 — Add market-regime walk-forward backtest output · Codex
**Why:** The remaining non-human research follow-up was to verify whether the
volume-PIT `mean_reversion`×`CHOP` edge was temporally stable or concentrated in
one episode. The existing walk-forward table was setup-level only, so it could
not answer the CHOP-specific question directly.
**Changes:**
- Added setup×BTC-market walk-forward reporting to `backtest --walk-forward`,
  using the same full-period same coin-regime×BTC-market base-rate convention as
  the existing market-regime edge table.
- Added unit coverage for the new market-regime walk-forward formatter.
- Added `research/VOLUME_PIT_WALK_FORWARD_2026-06-17.md` with the comparable
  top-100/1825d volume-PIT walk-forward result.
- Updated `AGENTS.md` and `ROADMAP.md` with the result.
**Verify:** `make verify` passed with 262/262 tests, alert render smoke, fixture
backtest smoke, and paper scoreboard. `.venv/bin/python -m
crypto_rsi_scanner.backtest --pit-volume --top-n 100 --days 1825
--walk-forward` completed with 368 usable coins and 21,334 graded observations;
`mean_reversion`×`CHOP` test-fold edges were +2, +25, +26.
**Notes/risks:** Research/reporting only. This does not alter live conviction,
routing, alerts, paper trading, or registry priors.

## 2026-06-17 — Surface external assets in event-fade review artifacts · Codex
**Why:** The latest no-key review bundle had valid machine `external_asset`
values, but the editable review sidecars and packets did not show them. That
made proxy rows look like they lacked a concrete external catalyst and made
manual review more error-prone.
**Changes:**
- Added `external_asset` to event-fade review-template CSV/JSONL rows and to the
  human-readable review packet event line.
- Updated the review-bundle README/guide text so reviewers know to verify the
  machine-extracted external catalyst before assigning `valid_proxy_fade`.
- Added regression coverage for sidecar, packet, CSV, and bundle headers.
- Rebuilt `/tmp/event_fade_no_key_review_bundle_20260617_external_assets` from
  the existing research cache so `review_template_balanced.csv` now surfaces
  catalyst identities such as `SpaceX` and `World Cup`.
**Verify:** `make verify` passed with 262/262 tests, alert render smoke, fixture
backtest smoke, and paper scoreboard.
**Notes/risks:** Review-artifact only. This does not change event discovery,
classification, event-fade scoring, alerts, storage, paper trades, or promotion
status.

## 2026-06-17 — Guard external-asset extraction and refresh no-key bundle · Codex
**Why:** A live no-key refresh showed the new generic extractor could over-capture
headline action phrases, turning "Ventuals winds down on-chain pre-IPO markets"
into a fake external asset. This is exactly the false-positive pressure the
event-fade stabilization pass is meant to catch before human review.
**Changes:**
- Added an action-word guard to the rule-based external-asset normalizer so
  phrases like "winds down pre-IPO markets" are rejected instead of becoming
  proxy catalysts.
- Added regression coverage proving generic IPO entities still extract
  (`Mercury`, `Cerebras`) while the pre-IPO-market shutdown headline leaves
  `external_asset` blank.
- Regenerated the no-key review bundle at
  `/tmp/event_fade_no_key_review_bundle_20260617_external_assets` using a fresh
  `/tmp/event_fade_no_key_cache_20260617_external_assets` cache.
- Updated `ROADMAP.md` and `research/event_discovery_design.md` with the cleaned
  bundle counts and extractor guardrail.
**Verify:** Targeted extractor tests passed. The refreshed bundle has 121 rows:
26 proxy candidates, 19 proxy-context controls, 8 direct rows, 68 ambiguous rows,
117 missing machine event times, 0 triggers, and the bad external asset is gone.
GDELT timed out during the refresh and wrote a zero-row diagnostic; RSS and
Polymarket produced the review bundle.
**Notes/risks:** Research/review workflow only. The bundle still has no reviewed
labels or trigger outcomes, so promotion remains blocked on human labeling.

## 2026-06-17 — Broaden rule-based external asset extraction · Codex
**Why:** The Pro-model review flagged that proxy-news discovery still depended
too heavily on a short hardcoded external-asset list. That left likely future
IPO/proxy candidates invisible unless the company name was already enumerated.
**Changes:**
- Expanded the news external-asset alias list with common private-company proxy
  targets from the public RSS search set (`Stripe`, `Databricks`, `Anduril`,
  `Figma`, `xAI`) plus `Kraken`.
- Added conservative capitalized-entity extraction for explicit
  IPO/public-debut, synthetic-exposure, tokenized-share, prediction-market, and
  sports-match phrasing.
- Reused the same extractor for live Polymarket/Gamma prediction-market rows.
- Added regression tests for generic company names such as `Mercury` and
  `Cerebras`, plus a `USA vs Paraguay` sports-match catalyst.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document the extractor as
  radar/review-only evidence.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 262/262.
**Notes/risks:** This does not add providers, alerts, paper trades, or live
routing. Extracted external assets still have to survive resolver confidence,
proxy/direct classification, event-time confidence, and the event-fade hard
gate before they can become anything beyond review evidence.

## 2026-06-17 — Add source providers to event-fade review aids · Codex
**Why:** The review sidecar already summarized source origins, but reviewers
also need provider visibility (`project_blog_rss`, `gdelt`,
`prediction_market_events`, etc.) while labeling for the source-provider
diversity gate.
**Changes:**
- Added `source_providers` as a helper-only review-template column and review
  packet section; it is excluded from evidence matching/copyback just like
  `source_search_url` and `source_date_hint`.
- Updated the review bundle README/guide text, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document the new reviewer aid.
- Added regression coverage for packet output, sidecar CSV round-tripping,
  helper-only apply behavior, and review-bundle artifacts.
- Regenerated the latest no-key review bundle at
  `/tmp/event_fade_no_key_review_bundle_20260617_050822_source_providers`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 260/260.
`make verify` passes with 260/260 tests, alert render smoke, fixture backtest
smoke, and paper scoreboard. The regenerated balanced sidecar has 75 rows,
includes `source_providers`, and still orders the 25 proxy rows as 15
`proxy_instrument` rows followed by 10 `proxy_venue` rows.
**Notes/risks:** Review-workflow only. This does not change event scoring,
eligibility gates, alerts, live storage, paper trades, or promotion status.

## 2026-06-17 — Prioritize proxy instruments in review sidecar · Codex
**Why:** The latest balanced review sidecar spent too much proxy-review capacity
on `proxy_venue` rows even though proxy venues are watchlist/review-only by
default. The validation sample should first cover the actual proxy instruments
that could eventually test the event-fade thesis.
**Changes:**
- Changed balanced proxy review selection to choose `proxy_instrument` rows
  first, then fill remaining proxy slots with other proxy roles such as
  `proxy_venue`.
- Added a regression test proving proxy instruments take priority over proxy
  venues while still using venues as fill when the proxy-instrument pool is too
  small.
- Regenerated the latest review bundle into
  `/tmp/event_fade_no_key_review_bundle_20260617_050822_instrument_first`.
- Updated `ROADMAP.md` so the human labeling task points at the instrument-first
  bundle.
**Verify:** `make verify` passes with 260/260 tests plus alert render smoke,
fixture backtest smoke, and paper scoreboard. The regenerated balanced sidecar
has 25 proxy rows: all 15 available `proxy_instrument` rows first, then 10
`proxy_venue` rows.
**Notes/risks:** Review-workflow only. This changes local sidecar ordering and
sample review priority, not event-fade scoring, alerts, storage, paper trades,
or promotion gates.

## 2026-06-17 — Refresh no-key event-fade review bundle · Codex
**Why:** The Pro-model plan calls for running discovery cycles and building a
reviewed validation sample. The previous bundle was already stale relative to
the current source mix and sidecar preflight workflow.
**Changes:**
- Ran `make event-fade-no-key-review-cycle` with a fresh temp cache and
  1h outcome-price export enabled.
- Produced `/tmp/event_fade_no_key_review_bundle_20260617_050822_fresh` from
  public RSS, GDELT, and Polymarket no-key sources.
- The bundle has 128 validation rows: 26 proxy candidates, 21 proxy-context
  controls, 8 direct rows, 73 ambiguous rows, 124 missing machine event times,
  0 eligible rows, and 0 triggers.
- The balanced sidecar still provides 75 review rows: 25 proxy candidates and
  50 controls. Its README/guide include the sidecar preflight command before
  apply.
- Updated `ROADMAP.md` so the human labeling task points at the fresh bundle.
**Verify:** Inspected the generated `manifest.json`, `review_report.txt`,
`labeling_queue.txt`, and `review_template_balanced.csv`. The bundle manifest
shows 128 sample rows and 75 balanced review rows; the balanced sidecar has 13
source date hints. `make verify` passes with 259/259 tests plus alert render
smoke, fixture backtest smoke, and paper scoreboard.
**Notes/risks:** Artifact refresh only. It does not infer labels, promote
event-fade, route alerts, write live signal/paper tables, or open paper trades.
The validation plan remains blocked on human labels and confirmed event times.

## 2026-06-17 — Add review sidecar preflight check · Codex
**Why:** The remaining event-fade work depends on human-edited sidecars. Before
those labels are copied into validation samples, reviewers need a dry check that
catches stale evidence, missing provenance, incomplete trigger outcomes, and
valid proxy labels without explicit catalyst timing.
**Changes:**
- Added `check_review_template()` and `format_review_template_check()` to dry-run
  edited sidecars against a validation sample without writing output.
- Added `main.py --event-fade-check-review-template SAMPLE TEMPLATE` and
  `make event-fade-check-review-template`.
- Tightened the labeling queue so `valid_proxy_fade` proxy rows with missing or
  weak machine event times remain queued until `human_event_time_source` and
  high-confidence human event-time confirmation are supplied.
- Updated review-bundle README/guide text plus `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to place the check before sidecar apply.
- Added regression coverage for ready sidecars, changed-evidence sidecars, and
  valid proxy labels missing explicit catalyst timing.
- Refreshed the latest no-key review bundle into
  `/tmp/event_fade_no_key_review_bundle_20260617_032443_template_check`; its
  README/guide now include the dry-check step, with the same 121 sample rows, 75
  balanced review rows, and 13 source date hints.
**Verify:** `make -n event-fade-check-review-template
EVENT_FADE_SAMPLE_IN=/tmp/sample.jsonl EVENT_FADE_REVIEW_TEMPLATE=/tmp/review.csv`
prints the expected CLI command. `make verify` passes with 259/259 tests plus
alert render smoke, fixture backtest smoke, and paper scoreboard.
**Notes/risks:** Review workflow only. The check writes nothing and does not
infer labels, change event-fade scoring, route alerts, write live signal/paper
tables, or open paper trades.

## 2026-06-17 — Add source date hints to event-fade review aids · Codex
**Why:** The no-key event-fade bundle still has many rows with missing machine
event times. Reviewers need fast, local cues from source titles/event names to
spot likely catalyst dates without letting the machine infer or promote weak
event times.
**Changes:**
- Added a derived `source_date_hint` helper column to event-fade review
  templates and balanced templates.
- Added matching `Source date hint` lines to review packets and documented the
  helper in bundle README/guide text.
- Kept the field review-only: it is excluded from sidecar evidence matching and
  is not copied back into validation samples.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`.
- Refreshed the latest no-key review bundle into
  `/tmp/event_fade_no_key_review_bundle_20260617_032443_date_hints`; its
  balanced sidecar still covers 75 gate rows and now includes 13 rows with date
  hints.
**Verify:** `.venv/bin/python -m compileall -q crypto_rsi_scanner tests` passed.
`make verify` passes with 257/257 tests plus alert render smoke, fixture
backtest smoke, and paper scoreboard. The regenerated bundle manifest still
reports 121 total rows and 75 balanced review rows.
**Notes/risks:** Review workflow only. This does not infer labels, change
event-fade scoring, promote event-fade, route alerts, write live signal/paper
tables, or open paper trades.

## 2026-06-17 — Diversify balanced event-fade review rows · Codex
**Why:** The balanced event-fade sidecar now covered proxy and control gates,
but the control slice still clustered heavily around repeated BTC/news rows.
The validation sample needs broad asset/event/source coverage before any edge
claim is meaningful.
**Changes:**
- Changed the balanced review selector to choose rows diversity-first within
  each slice, reducing repeats by asset, event type, asset role, relationship,
  source origin, and event title while leaving the strict priority queue
  unchanged.
- Fixed zero limits for balanced slices so `proxy_limit=0` or
  `triggered_limit=0` really selects no rows for that slice.
- Added a regression test proving the strict priority template can still pick
  repeated controls while the balanced template spreads the same sample across
  different assets.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`.
- Refreshed the latest no-key review bundle into
  `/tmp/event_fade_no_key_review_bundle_20260617_032443_diverse_balanced`; its
  50-control slice now spans 22 assets instead of being BTC-dominated.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 256/256
tests. The regenerated bundle manifest includes the same 75 balanced rows.
**Notes/risks:** Review workflow only. This does not infer labels, promote event
fade, route alerts, write live signal/paper tables, or change event-fade
scoring.

## 2026-06-17 — Add balanced event-fade review packet · Codex
**Why:** The balanced review CSV is now the preferred handoff for building the
proxy/control validation sample, but its matching evidence packet was still the
strict-priority packet. Reviewers need a Markdown packet with the same rows and
slice labels as `review_template_balanced.csv`.
**Changes:**
- Added `format_balanced_review_packet()` and shared balanced-row selection for
  the balanced review sidecar and packet.
- Event-fade review bundles now write `review_packet_balanced.md`, include it in
  `manifest.json`, and point the README workflow at it.
- Review packets now include the derived `source_search_url` helper line when
  available, so Google News/feed wrapper rows can be checked from Markdown too.
- Updated bundle tests plus `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`.
- Refreshed the latest no-key review bundle into
  `/tmp/event_fade_no_key_review_bundle_20260617_032443_balanced_packet`; its
  balanced sidecar and balanced packet cover 75 gate rows: 25 proxy candidates
  and 50 controls.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 255/255
tests. The regenerated bundle manifest includes `review_packet_balanced.md`.
**Notes/risks:** Review workflow only. No labels are inferred, no live storage
or alerts are written, no paper trades are opened, and event-fade promotion
remains blocked on human-reviewed evidence.

## 2026-06-17 — Add source search links to review sidecars · Codex
**Why:** The latest balanced review bundle has many Google News/feed wrapper
links, which slows human review because the canonical article can be harder to
open directly. Reviewers need a fast fallback link without introducing network
resolution, scraping, or auto-labeling.
**Changes:**
- Added `source_search_url` to event-fade review templates and balanced review
  templates.
- The search URL is generated from the raw title plus source origin/publisher so
  reviewers can find the canonical article when `primary_source_url` is a feed
  or Google News wrapper.
- Kept `source_search_url` as a derived helper column excluded from evidence
  matching and review-field copying.
- Updated generated bundle README/guide text plus `AGENTS.md`, `ROADMAP.md`,
  and `research/event_discovery_design.md`.
- Refreshed the latest no-key review bundle into
  `/tmp/event_fade_no_key_review_bundle_20260617_032443_searchlinks`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 255/255
tests.
**Notes/risks:** This is review-workflow only. It performs no network
resolution, does not infer labels, and does not change event-fade scoring,
routing, storage, paper trading, or promotion gates.

## 2026-06-17 — Add balanced event-fade review sidecar · Codex
**Why:** The priority review template focused entirely on proxy event-time rows
in the current no-key bundle, but the validation gate also needs 50 direct or
ambiguous controls. Reviewers need one sidecar that can build the proxy/control
sample in parallel.
**Changes:**
- Added `review_template_balanced.csv` to event-fade review bundles.
- Added `build_balanced_review_template_rows`, which includes triggered rows,
  up to 25 proxy candidates, and up to 50 direct/ambiguous negative controls
  using the same strict sidecar fields and evidence matching as the normal
  priority template.
- Added a `review_slice` helper column so reviewers can see whether a row is in
  the triggered, proxy-candidate, or negative-control slice.
- Updated bundle manifests, README text, review guide text, `AGENTS.md`,
  `ROADMAP.md`, and `research/event_discovery_design.md`.
- Refreshed the latest no-key review bundle into
  `/tmp/event_fade_no_key_review_bundle_20260617_032443_balanced`; its balanced
  sidecar contains 75 rows: 25 proxy candidates and 50 controls.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 255/255
tests.
**Notes/risks:** This is review-workflow only. It does not infer labels, alter
event-fade scoring, route alerts, write live DB signal/paper tables, or promote
event fade beyond local reports.

## 2026-06-17 — Add review-template helper columns · Codex
**Why:** The event-fade validation sample is blocked on human review, and the
CSV sidecar was too machine-oriented for fast spreadsheet labeling. Reviewers
needed a primary source link, source title, and compact prompt without weakening
the strict reviewed-evidence rules.
**Changes:**
- Added reviewer-only `review_prompt`, `event_time_review_hint`,
  `primary_source_url`, `primary_source_origin`, and `primary_raw_title` columns
  to event-fade review templates.
- Kept those helper columns out of review-field copying and evidence matching so
  changing them cannot create or invalidate reviewed evidence.
- Updated generated review bundle README/guide text to explain that helper
  columns are aids only; counted review fields remain `review_status`,
  `reviewed_by`, `reviewed_at`, `human_label`, `human_notes`,
  `human_event_time*`, and required outcome fields.
- Refreshed the latest no-key review bundle into
  `/tmp/event_fade_no_key_review_bundle_20260617_032443_with_helpers`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 254/254
tests.
**Notes/risks:** This is review-workflow only. It does not infer labels, alter
event-fade scoring, route alerts, write live DB signal/paper tables, or promote
event fade beyond local reports.

## 2026-06-17 — Generate fresh no-key event-fade review bundle · Codex
**Why:** The event-fade pipeline is now blocked on reviewed evidence, not more
provider code. A fresh no-key run gives the human a concrete bundle to label and
shows what the current public-source discovery pass can actually produce.
**Changes:**
- Ran `make event-fade-no-key-review-cycle` into
  `/tmp/event_fade_no_key_review_bundle_20260617_032443` with 1h outcome-price
  export enabled.
- Confirmed the run produced 121 review rows: 27 proxy candidates, 19
  proxy-context controls, 8 direct-beneficiary rows, 67 ambiguous rows, 0
  eligible rows, 0 SHORT_TRIGGERED rows, and 117 rows missing machine event
  times.
- Noted that GDELT failed soft with HTTP 429, while RSS/Google News and
  Polymarket produced cache evidence.
- Added a ROADMAP checkpoint pointing reviewers at the generated bundle and the
  exact remaining human-labeling work.
**Verify:** `make event-discovery-status`; `make event-fade-no-key-review-cycle
EVENT_DISCOVERY_CACHE_DIR=/tmp/event_fade_no_key_cache_20260617_032443
EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=/tmp/event_fade_no_key_review_bundle_20260617_032443
EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1 EVENT_FADE_PRICE_INTERVAL=1h`.
**Notes/risks:** This is a research artifact checkpoint only. The run wrote temp
cache/review-bundle files and did not route alerts, write live DB signal/paper
tables, or promote event fade beyond local review.

## 2026-06-17 — Gate event-fade promotion on review provenance · Codex
**Why:** Review provenance fields existed, but a reviewed row missing
`reviewed_by` or `reviewed_at` could still look mechanically complete in review
metrics. The validation sample needs auditable labels before any future
promotion decision.
**Changes:**
- Added `missing_review_provenance_rows` to event-fade validation review metrics,
  formatted reports, bundle manifests, and bundle README gate summaries.
- Added a promotion blocker and next-sample-work item for reviewed rows missing
  `reviewed_by`/`reviewed_at`.
- Added an `add_review_provenance` labeling-queue category before PIT/source
  checks so incomplete reviewed rows surface in review packets/templates.
- Updated `AGENTS.md`, `ROADMAP.md`, `research/event_discovery_design.md`, and
  the bundle guide to treat review provenance as a promotion blocker.
- Added regression coverage for missing provenance blocking promotion and being
  prioritized in the queue.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 254/254
tests, and `make verify` passes.
**Notes/risks:** This is artifact-only. It does not change event-fade scoring,
eligibility, live routing, storage, paper trading, or execution.

## 2026-06-17 — Add event-fade review provenance fields · Codex
**Why:** The validation workflow can preserve labels and outcomes across fresh
exports, but those labels were not traceable to a reviewer or review time. That
weakens the reviewed sample as evidence once rows are copied forward.
**Changes:**
- Added `reviewed_by` and `reviewed_at` to event-fade validation sample exports.
- Added both fields to review sidecar templates, sidecar apply, and
  evidence-safe reviewed-sample merges.
- Updated review packets, bundle guides, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to describe the provenance fields.
- Extended regression tests for sample export defaults, sidecar round-trip,
  reviewed-sample merge, scanner sidecar apply, and bundle guide content.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 253/253
tests, and `make verify` passes.
**Notes/risks:** This is artifact-only. It does not alter event-fade scoring,
eligibility, routing, paper trades, live DB writes, or promotion gates.

## 2026-06-17 — Add event-fade review guide bundles · Codex
**Why:** The review bundle had the evidence packet and editable sidecar, but it
still assumed reviewers already knew the accepted label taxonomy, proxy/direct
rules, event-time confirmation rules, and outcome fields. That made the next
human-labeling step easier to do inconsistently.
**Changes:**
- Added `review_guide.md` to event-fade review bundles with the accepted
  `human_label` values, proxy/direct criteria, human event-time confirmation
  fields, outcome fields, and promotion reminder.
- Included the guide in bundle manifests, README file lists, and suggested
  workflow steps.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  to document the new bundle artifact.
- Extended review-bundle regression tests to require the guide in normal,
  auto-price, and cache-backed bundles.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 253/253
tests, and `make verify` passes.
**Notes/risks:** This is an artifact-only review aid. It does not infer labels,
modify source samples, promote alerts, write live DB rows, or open paper trades.

## 2026-06-17 — Use human event times in validation metrics · Codex
**Why:** Human-confirmed event times were being preserved in review artifacts,
but validation metrics still ignored them. That would keep confirmed proxy rows
blocked or mismeasured even after manual review.
**Changes:**
- Taught validation outcome filling to use a high-confidence
  `human_event_time` for event-time baseline outcomes when the machine
  `event_time` is missing or weaker.
- Taught review metrics to use high-confidence human event times for
  review-only decision timing, trigger latency, low-confidence trigger-time
  checks, point-in-time checks, and event-time-source cohorts.
- Kept machine-derived `event_time` unchanged so reviewed timing evidence stays
  separate from what the discovery pipeline knew automatically.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the review-only interpretation.
- Added regression coverage for outcome filling and promotion-review metrics on
  a triggered proxy row with only `human_event_time`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 253/253
tests, and `make verify` passes.
**Notes/risks:** This does not promote event fade, alter discovery eligibility,
route alerts, write live DB rows, or open paper trades. It only makes manual
validation artifacts measurable after reviewers confirm catalyst times.

## 2026-06-17 — Add human event-time review fields · Codex
**Why:** The expanded no-key RSS cycle produced many proxy-instrument leads, but
nearly all lacked confirmed catalyst times. Reviewers need a first-class,
artifact-only way to confirm event times without overwriting what the system
actually extracted.
**Changes:**
- Added `human_event_time`, `human_event_time_source`,
  `human_event_time_confidence`, and `human_event_time_notes` to validation
  samples, review templates, and sidecar apply copying.
- Prioritized unlabeled proxy rows with missing/weak/non-explicit event times as
  `confirm_proxy_event_time` in the labeling queue before ordinary proxy labels.
- Updated review packets, bundle README text, `AGENTS.md`, and
  `research/event_discovery_design.md` to explain that human event-time
  confirmation stays separate from machine-derived `event_time`.
- Added regression coverage for queue prioritization and sidecar round-tripping
  of human event-time confirmations without changing original event evidence.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 252/252
tests, and `make verify` passes. A cache-review-bundle smoke against
`/tmp/event_fade_expanded_rss_cache` wrote `/tmp/event_fade_event_time_review_bundle`
with `confirm_proxy_event_time` queue rows and `human_event_time*` columns in
`review_template.csv`.
**Notes/risks:** This is review-artifact plumbing only. It does not make
event-fade eligible, route alerts, write live DB rows, open paper trades, or
convert human-confirmed times into system-discovered catalyst times.

## 2026-06-17 — Broaden no-key proxy RSS searches · Codex
**Why:** The first no-key review cycle produced mostly ambiguous controls and
only one proxy-venue row. Before adding more providers, the public RSS starter
list should better target dated proxy-instrument evidence.
**Changes:**
- Expanded `fixtures/event_discovery/public_rss_feeds.txt` from one targeted
  Google News search to several searches covering pre-IPO/synthetic exposure,
  tokenized stocks, fan tokens, prediction markets, sports, and political proxy
  narratives.
- Added an offline regression test that keeps the checked-in RSS list focused
  on proxy-instrument research terms.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the expanded no-key RSS behavior.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 251/251
tests, and `make verify` passes. A focused public-RSS research smoke into
`/tmp/event_fade_expanded_rss_bundle` collected 381 raw rows, 350 normalized
events, 118 candidate snapshots, 27 proxy candidates, and 16 proxy-instrument
rows; all remained `NO_TRADE` because 117/118 rows lacked confirmed event time.
**Notes/risks:** This improves collection targeting only. It does not promote
event fade beyond research reports. Rows still need human labels/outcomes, and
the next data-quality gap is event-time confirmation for proxy-instrument leads.

## 2026-06-17 — Run no-key event-fade review cycle · Codex
**Why:** After the stabilization pass, the next Pro-plan step was to run the
research collection workflow and see whether it produced reviewable proxy-fade
evidence.
**Changes:**
- Ran `make event-fade-no-key-review-cycle` with 1h outcome price export enabled
  and wrote a local review bundle under `/tmp/event_fade_no_key_review_bundle`.
- Added `research/EVENT_FADE_NO_KEY_REVIEW_CYCLE_2026-06-17.md` summarizing the
  run, bundle contents, provider results, blockers, and next review work.
- Updated `ROADMAP.md` with the fresh 69-row bundle status and sample gaps.
**Verify:** No-key cycle completed; RSS/Google News produced 66 candidate
snapshots, Polymarket produced 3, GDELT returned HTTP 429, and the generated
bundle reported 69 rows needing review, 0 eligible rows, and 0 triggers.
**Notes/risks:** The sample is still unreviewed. The only proxy row was a
`proxy_venue` HYPE/SpaceX row and was correctly forced `NO_TRADE`; next work is
human labeling plus better dated proxy-instrument collection.

## 2026-06-17 — Stabilize event-fade discovery validation · Codex
**Why:** The event-discovery pipeline had grown into a real research factory,
but the next risk was weak evidence accidentally looking tradable before a
reviewed validation sample exists. The review also flagged source-export and
review-artifact ergonomics that should be fixed before sharing the repo again.
**Changes:**
- Added clean source sharing support: `.gitattributes` export ignores for local
  artifacts, `make export-src`, `make bootstrap`, `PYTHON ?=`, and a helpful
  missing-runtime check for `make verify`.
- Added explicit discovery gates that force `NO_TRADE` for low classifier
  confidence, low event-time confidence, and proxy-venue rows by default
  (`RSI_EVENT_FADE_ALLOW_PROXY_VENUE_TRIGGER=0`).
- Added canonical catalyst dedupe and point-in-time-safe merged enrichment
  selection across deduped raw sources.
- Added research-cache transition timestamps for first seen/watchlisted/armed/
  triggered and last seen candidate snapshots.
- Added 1d/1h validation price export support and outcome interval/source
  metadata in filled samples/review packets.
- Updated `AGENTS.md`, `DECISIONS.md`, `ROADMAP.md`,
  `research/event_discovery_design.md`, and `.env.example`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 250/250
tests, and `make verify` passes.
**Notes/risks:** Event-fade remains research-only: no Telegram routing, paper
trades, live DB writes, or execution. The next useful work is still building and
labeling the reviewed event-fade sample, not adding more providers.

## 2026-06-17 — Surface source origins in review aids · Codex
**Why:** Source-origin diversity is now measured in validation reviews, but the
manual labeling artifacts still forced reviewers to infer publisher/domain
concentration from raw URLs and titles. The row-level review workflow should
show that context directly.
**Changes:**
- Added derived `source_origins` to event-fade labeling queue items and review
  template rows.
- Added source-origin lines to `--event-fade-labeling-queue` output and
  `--event-fade-review-packet` Markdown rows.
- Marked `source_origins` as a derived review-template field so regenerated
  publisher inference does not create noisy sidecar evidence-change blockers.
- Added regression coverage for Google News publisher extraction in queues and
  templates, and for source-origin rendering in review packets.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 245/245
tests, and `make verify` passes.
**Notes/risks:** Artifact-only validation workflow change. No changes to event
discovery, event-fade scoring, alerts, paper trades, live storage, or promotion
automation.

## 2026-06-17 — Surface event-fade source-origin diversity · Codex
**Why:** The event-fade validation review already checks source-provider
diversity, but RSS and Google News rows can hide multiple independent publishers
behind one ingestion provider. Reviewers need domain/publisher concentration
visible before treating a sample as broad evidence.
**Changes:**
- Added source-origin derivation from validation row `source_urls`, with Google
  News wrapper links falling back to publisher suffixes in `raw_titles`.
- Added reviewed proxy source-origin counts and source-origin cohorts to
  `--event-fade-review-sample`.
- Added source-origin counts and per-origin quality summaries to review bundle
  manifests and READMEs.
- Added regression coverage for normal URL-domain origins and Google News
  publisher suffix extraction.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes with 245/245
tests, and `make verify` passes.
**Notes/risks:** This is validation/reporting only. It does not change event
discovery, event-fade scoring, validation thresholds, alerts, paper trades,
live storage, or promotion automation.

## 2026-06-16 — Add GDELT to no-key event-fade review cycle · Codex
**Why:** The no-key validation workflow needs broader independent source
coverage than public RSS plus Polymarket. GDELT was already implemented as an
opt-in no-key news source, but it lacked a Make convenience target and was not
part of the mixed review cycle.
**Changes:**
- Added `make event-discovery-refresh-gdelt` and
  `make event-fade-gdelt-review-cycle` with configurable query, record limit,
  30-day lookback, and live CoinGecko universe enrichment defaults.
- Updated `make event-fade-no-key-review-cycle` so it now runs public RSS,
  GDELT, and Polymarket into one observational cache before writing the review
  bundle.
- Added Make dry-run regression tests covering the new GDELT target and the
  expanded no-key aggregate cycle.
- Updated `AGENTS.md`, `ROADMAP.md`, `.env.example`, and
  `research/event_discovery_design.md` with the new workflow.
**Verify:** `make -n event-fade-gdelt-review-cycle`, `make -n
event-fade-no-key-review-cycle`, `.venv/bin/python tests/test_indicators.py`
with 244/244 passing, and `make verify` all pass. A temp live
`make event-fade-gdelt-review-cycle` failed soft on GDELT HTTP 429 and wrote an
empty review bundle; a temp live `make event-fade-no-key-review-cycle` still
completed from RSS/Polymarket with 41 review rows despite the GDELT 429.
**Notes/risks:** This is research workflow plumbing only. It does not change
event-fade scoring, validation thresholds, alerts, paper trades, live storage,
or promotion. GDELT is currently rate-limited in this environment, so it may
need a smaller query/window or retry later before it contributes rows.

## 2026-06-16 — Expose review gates in event-fade bundles · Codex
**Why:** The no-key review bundle is the handoff artifact for human and external
review, but its manifest/README only exposed a subset of the validation gates.
Source-provider diversity and timing blockers should be visible without parsing
the full text report.
**Changes:**
- Added review-gate metrics to review-bundle `manifest.json`, including proxy
  event-type/source-provider diversity, trigger BTC-risk diversity,
  low-confidence trigger event times, and event-time baseline gaps.
- Added a compact `Review gates` section to bundle `README.md`.
- Covered the enriched manifest and README fields in review-bundle regression
  tests.
**Verify:** `make verify` passes, including 243/243 tests, alert render smoke,
backtest fixture smoke, and paper scoreboard.
**Notes/risks:** This is review artifact metadata only. It does not change event
discovery, validation thresholds, event-fade scoring, alerts, paper trades, or
live storage.

## 2026-06-16 — Gate validation on source-provider diversity · Codex
**Why:** The no-key event-fade review workflow can collect many rows from one
RSS/feed/API source. A reviewed proxy sample should not look promotion-ready
unless the evidence spans independent source providers.
**Changes:**
- Added reviewed proxy source-provider counts and a default two-provider
  diversity gate to event-fade validation review.
- Added source-provider cohorts to the formatted review report.
- Added next-sample guidance when enough proxy rows exist but they all come
  from too few source providers.
- Added regression coverage for the positive multi-provider fixture sample and
  the single-source proxy blocker.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`.
**Verify:** `make verify` passes, including 243/243 tests, alert render smoke,
backtest fixture smoke, and paper scoreboard.
**Notes/risks:** This is validation/reporting only. It does not change event
discovery, event-fade scoring, alerts, paper trades, live storage, or promotion
automation.

## 2026-06-16 — Surface event-time confirmation in validation queue · Codex
**Why:** Low-confidence trigger event times already block promotion, but the
labeling queue could still treat a triggered row as complete once labels and
outcomes were filled. Reviewers need that timing issue surfaced as concrete
queue work.
**Changes:**
- Added event-time source/confidence to validation labeling queue items and
  formatted queue output.
- Added a `confirm_trigger_event_time` queue category for reviewed
  `SHORT_TRIGGERED` rows below the event-time confidence threshold.
- Reused one queue sort key for labeling queues, review packets, and review
  templates, ranking explicit/high-confidence event times before weaker
  source-text or missing event times inside the same review bucket.
- Added regression coverage for low-confidence triggered rows and same-priority
  event-time quality ordering.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`.
**Verify:** `make verify` passes, including 242/242 tests, alert render smoke,
backtest fixture smoke, and paper scoreboard.
**Notes/risks:** This is artifact-only review workflow behavior. It does not
change event discovery, event-fade scoring, alert routing, paper trades, live
storage, or promotion thresholds.

## 2026-06-16 — Gate validation on event-time confidence · Codex
**Why:** Source-text date inference is useful for review, but a validation
sample should not become promotion-ready when triggered examples rely on weak
event-time evidence.
**Changes:**
- Added event-time-source cohorts to event-fade validation review reports.
- Added a low-confidence trigger event-time count and promotion blocker for
  reviewed `SHORT_TRIGGERED` rows below the event-time confidence threshold.
- Added next-sample guidance to confirm low-confidence trigger times from
  explicit source evidence.
- Covered promotion-ready explicit timing and blocked `text_date` trigger
  timing in regression tests.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`.
**Verify:** `make verify` passes, including 240/240 tests, alert render smoke,
backtest fixture smoke, and paper scoreboard.
**Notes/risks:** This is validation/reporting only. It does not change event
discovery, scoring, alert routing, paper trades, or live storage.

## 2026-06-16 — Expose event-time provenance in validation · Codex
**Why:** Source-text date inference made more RSS rows dated, but reviewers also
need to see whether a timestamp came from explicit provider data or lower-
confidence text parsing. The fade gate should not treat those sources as equal.
**Changes:**
- Added `event_time_source` to normalized events and validation sample exports.
- Added event-time source/confidence to review packets and compact review
  templates so review merges detect timing-provenance changes.
- Capped fade-candidate confidence by `event_time_confidence`, preventing
  lower-confidence `text_date` rows from silently satisfying the event-fade
  confidence gate.
- Added regression coverage for `text_date` exports, review packet/template
  fields, and confidence-capped `NO_TRADE` behavior.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`.
**Verify:** `make verify` passes, including 239/239 tests, alert render smoke,
backtest fixture smoke, and paper scoreboard.
**Notes/risks:** This preserves source-text dates as reviewable evidence, not
promotion evidence. Explicit provider times and higher-confidence external
catalyst rows still work normally.

## 2026-06-16 — Infer dated catalysts from news text · Codex
**Why:** Public RSS produced proxy leads, but most were stuck as undated
`proxy_attention` rows. The validation sample needs more dated review evidence
without weakening the event-fade hard gate.
**Changes:**
- Added conservative source-text date inference to shared news/RSS parsing for
  phrases like "by June 20, 2026" or "on 2026-06-20".
- Tagged inferred dates as lower-confidence `event_time_source=text_date`
  evidence instead of treating them like explicit provider timestamps.
- Added regression coverage for dated RSS proxy rows becoming `proxy_exposure`
  review candidates while undated proxy rows stay `proxy_attention`/`NO_TRADE`.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`.
**Verify:** `make verify` passes, including 239/239 tests, alert render smoke,
backtest fixture smoke, and paper scoreboard. A live `make
event-fade-no-key-review-cycle` run in `/tmp` produced a 67-row mixed bundle
with missing event-time rows reduced to 57, but still no dated proxy-fade
candidate or trigger.
**Notes/risks:** This is research evidence only. Inferred dates use source text,
not publication time, and cannot bypass link/classifier confidence, proxy/direct
eligibility, pre-event pump, or post-event failure gates.

## 2026-06-16 — Combine no-key event-fade review sources · Codex
**Why:** Public RSS and Polymarket each contribute different useful validation
evidence, but running them separately left reviewers with split bundles and no
source-level quality breakdown.
**Changes:**
- Added `make event-fade-no-key-review-cycle` to run public RSS and Polymarket
  refreshes into the same research cache before writing one review bundle.
- Added `source_provider_summary` to review bundle manifests and README output,
  showing per-provider row, proxy/direct, trigger, and missing-time counts.
- Covered the combined Make wiring plus normal and empty review-bundle source
  summaries in regression tests.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`.
**Verify:** `make verify` passes, including 238/238 tests, alert render smoke,
backtest fixture smoke, and paper scoreboard. `make
event-fade-no-key-review-cycle` in `/tmp` fetched 138 RSS raw rows and 35
Polymarket raw rows, producing a 68-row mixed review bundle with 3 RSS proxy
leads and 3 dated Polymarket controls.
**Notes/risks:** This stays review-only: no live DB writes, alerts, paper
trades, or event-fade promotion. Current no-key sources still need human
labels/outcomes before they prove edge.

## 2026-06-16 — Add no-key Polymarket catalyst discovery · Codex
**Why:** The fresh public RSS review bundle produced review rows, but every row
was missing `event_time`, so it could only provide undated attention/control
leads. The validation workflow needs dated external catalysts too.
**Changes:**
- Added opt-in live Polymarket Gamma fetching to
  `event_providers/prediction_market_events.py`, preserving event end dates as
  `event_time` and preferring active nested market end dates when available.
- Wired `RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE` plus base URL,
  limit, and timeout settings through config, scanner, and provider readiness.
- Added `make event-discovery-refresh-polymarket` and
  `make event-fade-polymarket-review-cycle` for no-key research cache/review
  bundle generation.
- Hardened the resolver against the live Polymarket `BILL`/`bill` false
  positive where legislative text matched the Billions Network token.
- Updated `.env.example`, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`.
**Verify:** `make verify` passes, including 237/237 tests, alert render smoke,
backtest fixture smoke, and paper scoreboard. `make
event-fade-polymarket-review-cycle` in `/tmp` fetched 17 dated raw Polymarket
events, built one current ambiguous-control review row after the `BILL` guard,
and wrote a research-only review bundle.
**Notes/risks:** Polymarket currently adds useful dated control evidence, not
proxy-fade proof. It remains opt-in, fail-soft, research-only, and unable to
bypass the event-fade proxy/direct hard gate.

## 2026-06-16 — Summarize event-fade review bundles · Codex
**Why:** The public RSS validation workflow now produces cleaner rows, but a
reviewer still had to inspect the sample or report to understand whether a
fresh bundle contained real proxy candidates, proxy-context controls, direct
events, trigger rows, or mostly missing event times.
**Changes:**
- Added a compact `sample_summary` block to review-bundle `manifest.json` with
  event type, relationship, asset role, signal type, source-provider, proxy,
  direct, trigger, and missing-event-time counts.
- Added the same summary to bundle `README.md` for quick human triage before
  editing the review sidecar.
- Covered normal cache-backed bundles and empty-cache bundles in regression
  tests.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the review-bundle summary behavior.
**Verify:** `make verify` passes, including 234/234 tests, alert render smoke,
backtest fixture smoke, and paper scoreboard.
**Notes/risks:** This only changes local review artifacts. It does not affect
classification, event-fade scoring, alert routing, paper trades, or live
storage.

## 2026-06-16 — Add asset-role cohorts to event-fade review reports · Codex
**Why:** Asset-role classification made public RSS samples cleaner, but the
review summary still only grouped by event type, relationship type, and BTC
risk. Reviewers need to see whether the sample is dominated by real proxy
instruments/venues or by context-control rows.
**Changes:**
- Added `asset_role_cohorts` to the validation review model and formatted review
  report.
- Kept the cohort behavior aligned with the existing event-type, relationship,
  and BTC-risk cohort metrics.
- Added regression coverage that reviewed rows are counted by asset role and
  that the report includes the `By asset role` section.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the asset-role cohort workflow.
**Verify:** `make verify` passes, including 234/234 tests, alert render smoke,
backtest fixture smoke, and paper scoreboard. A local review of
`/tmp/event_fade_role_rss_bundle/validation_sample.jsonl` prints the new
`By asset role` section with `proxy_venue` and `proxy_instrument` rows.
**Notes/risks:** This is read-only validation reporting. It does not change
classification, event-fade scoring, alerts, paper trades, or live storage.

## 2026-06-16 — Add event-discovery asset-role classification · Codex
**Why:** The public RSS bundle started surfacing proxy-style rows, but it still
treated background mentions and infrastructure rows inside SpaceX/HYPE articles
as proxy candidates. That polluted the manual validation queue before any human
labeling.
**Changes:**
- Added asset-role metadata to `EventClassification`, validation exports,
  discovery/auto reports, review packets, and review templates.
- Classified proxy-style links as `proxy_instrument`, `proxy_venue`,
  `mentioned_asset`, `infrastructure`, `ticker_word_collision`, or
  `direct_beneficiary`.
- Demoted non-instrument proxy-context rows to `relationship_type=proxy_context`
  with `is_proxy_narrative=False`, so BTC treasury mentions, Solana chain rows,
  and common-word HYPE matches stay negative/control evidence.
- Kept role metadata as additive validation-sample fields and ignored those
  fields during review-field merge comparisons unless the relationship itself
  changes.
- Documented the durable rule in `DECISIONS.md` and the event-discovery design.
**Verify:** `make verify` passes, including 234/234 tests, alert render smoke,
backtest fixture smoke, and paper scoreboard. A fresh public RSS cycle wrote
137 raw / 135 normalized events and 64 candidate snapshots into
`/tmp/event_fade_role_rss_cache`; the review bundle had 64 rows, with proxy
rows reduced to 3 actual HYPE proxy-instrument/venue rows and 6 `proxy_context`
controls for BTC/SOL/common-word Hype noise.
**Notes/risks:** Venue-vs-infrastructure is still deterministic and may be too
strict in borderline "on Hyperliquid" articles. This remains review-only and
does not alter live routing, paper trading, or live DB writes.

## 2026-06-16 — Surface public RSS proxy-attention review rows · Codex
**Why:** The no-key public RSS review cycle was clean after removing fixture
aliases, but it produced no proxy rows because broad publisher feeds mostly
returned generic BTC/control news and the classifier dropped proxy-style
articles when no precise event time was known.
**Changes:**
- Added a targeted Google News RSS search feed to the public RSS starter list
  for pre-IPO, tokenized-stock, prediction-market, and fan-token narratives.
- Let news providers infer common external assets such as SpaceX/OpenAI and let
  proxy-style articles without an event time remain `proxy_attention` review
  rows while still staying `NO_TRADE` under the event-fade hard gate.
- Raised the public RSS cycle defaults to a 30-day lookback and a broader live
  CoinGecko resolver universe.
- Added generic identity guards in the resolver so common words such as `cash`,
  `real`, `just`, and `humanity` do not create high-confidence asset matches
  from real news text.
- Added offline regression coverage for no-event-time proxy review rows, public
  RSS Makefile wiring, and the generic identity guard.
**Verify:** The guarded public RSS refresh wrote 138 raw / 136 normalized events
and 65 candidate snapshots into `/tmp/event_fade_targeted_rss_guarded_cache`;
the review bundle had 65 rows, including 8 `proxy_attention` rows, all
`NO_TRADE` / `eligible=False`. `make verify` passes, including 233/233 tests,
alert render smoke, backtest fixture smoke, and paper scoreboard.
**Notes/risks:** The public RSS sample still contains review noise such as
infrastructure or mentioned-asset rows; the next sample-quality improvement is
a role classifier that separates proxy instrument from venue/chain/mentioned
asset. No live routing, paper trading, or live DB writes changed.

## 2026-06-16 — Keep fixture aliases out of real event-discovery cycles · Codex
**Why:** The first public-RSS review bundle worked, but it exposed a serious
validation-sample contamination issue: the default alias file was the fixture
alias file, so real RSS rows produced fake `TESTBTC` candidates alongside real
BTC candidates.
**Changes:**
- Changed the runtime default `RSI_EVENT_DISCOVERY_ALIASES_PATH` to the neutral
  checked-in `event_discovery_aliases.json`, which starts empty for real
  research sources.
- Explicitly injected `fixtures/event_discovery/asset_aliases.json` only in
  fixture-backed Make targets.
- Added a regression test that `make event-discovery-refresh-public-rss` does
  not inject the fixture alias file.
- Updated `.env.example`, `AGENTS.md`, and
  `research/event_discovery_design.md` to distinguish curated runtime aliases
  from fixture aliases.
**Verify:** A fresh no-key public RSS refresh into
`/tmp/event_fade_public_rss_cache2` collected 55 raw RSS events and produced 48
candidate snapshots; the resulting review sample had zero `TEST*` asset
symbols. `make verify` passes, including 231/231 tests, alert render smoke,
backtest fixture smoke, and paper scoreboard.
**Notes/risks:** The neutral alias file is intentionally empty. Real one-off
proxy tokens still need curated aliases added there or a clean CoinGecko
universe match; fixture aliases remain available for deterministic tests and
fixture reports only.

## 2026-06-16 — Add no-key public RSS review cycle · Codex
**Why:** The configured event-fade review cycle still had no ready event source
on this machine, so the validation workflow needed a credential-free way to
collect real news/RSS evidence before human labeling.
**Changes:**
- Added `RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH` support for newline
  RSS/Atom URL lists, merged with the existing comma-separated URL env var.
- Added `fixtures/event_discovery/public_rss_feeds.txt` with verified public
  crypto RSS feeds and a fail-soft warning note.
- Added `make event-discovery-refresh-public-rss` and
  `make event-fade-public-rss-review-cycle`, which opt into the public RSS list
  and live CoinGecko universe enrichment while still writing only research cache
  and review-bundle artifacts.
- Updated provider status, `.env.example`, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the no-key RSS workflow.
- Added offline tests for URL-file parsing/deduping and RSS provider readiness.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 230/230.
`make -n event-discovery-refresh-public-rss` and
`make -n event-fade-public-rss-review-cycle` expand to the expected opt-in env
wiring.
With `EVENT_DISCOVERY_CACHE_DIR=/tmp/event_fade_public_rss_cache`, `make
event-discovery-refresh-public-rss` collected 55 raw RSS events and wrote 71
candidate snapshots, and `make event-fade-cache-review-bundle` wrote a 71-row
temporary review bundle. `make verify` passes, including 230/230 tests, alert
render smoke, backtest fixture smoke, and paper scoreboard.
**Notes/risks:** This does not promote event-fade output or make live routes.
Public RSS publishers can rate-limit or change feeds; failures stay in
`discovery_runs.jsonl` diagnostics and the review bundle still needs human
labels/outcomes before any conclusion.

## 2026-06-16 — Add event-discovery run diagnostics report · Codex
**Why:** Refresh diagnostics were persisted in `discovery_runs.jsonl`, but a
reviewer still had to open JSONL by hand to see whether recent configured runs
collected events, built candidates, or hit zero-output warnings.
**Changes:**
- Added `event_cache.load_discovery_runs()` for recent cache run rows, newest
  first.
- Added `main.py --event-discovery-runs` and `make event-discovery-runs` with
  text and JSON output for recent run counts, provider readiness, and refresh
  warnings.
- Added tests for cache run ordering/limits and scanner text/JSON output.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the new post-refresh diagnostics
  workflow.
**Verify:** Fixture `make event-discovery-refresh` into `/tmp` followed by
`make event-discovery-runs` prints the recent run summary, and
`main.py --event-discovery-runs --json` returns the cached run payload.
`make verify` passes, including 228/228 tests, alert render smoke, backtest
fixture smoke, and paper scoreboard.
**Notes/risks:** This is read-only reporting over the local research cache. It
does not fetch providers, route alerts, open paper trades, or write live
storage.

## 2026-06-16 — Persist event-discovery refresh diagnostics · Codex
**Why:** Source-ready live refreshes can still produce zero rows because of rate
limits, forbidden endpoints, empty provider results, or unresolved raw events.
The cache run row needs to preserve that context so a later reviewer can tell
the difference between "no events existed" and "the source failed or built no
candidates."
**Changes:**
- Added a redacted `diagnostics` object to event-discovery `discovery_runs.jsonl`
  rows and the cache write result.
- `main.py --event-discovery-refresh` now records provider readiness and prints/
  caches refresh warnings for zero raw events or zero validation candidates.
- Added regression coverage for run diagnostics and source-ready zero-output
  refreshes without making network calls.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the run-diagnostics behavior.
**Verify:** Fixture `make event-discovery-refresh` into `/tmp` writes
`diagnostics.provider_status` and an empty `refresh_warnings` list for the
healthy fixture run. `make verify` passes, including 227/227 tests, alert render
smoke, backtest fixture smoke, and paper scoreboard.
**Notes/risks:** Diagnostics are redacted and observational only. They do not
change provider fetching, event scoring, alert routing, paper trading, or live
storage.

## 2026-06-16 — Warn on empty event-fade review bundles · Codex
**Why:** A configured-source refresh can be source-ready but still produce zero
candidate rows when live providers rate-limit, forbid access, or return no
usable evidence. The cache review bundle previously looked like a normal
completed workspace with `needing_review=0`, which could be misread as no
remaining validation work.
**Changes:**
- Added an explicit empty-review-bundle warning to CLI output,
  `README.md`, and `manifest.json` for `--event-fade-review-bundle` and
  `--event-fade-cache-review-bundle` when no validation rows are available.
- Added a regression test for empty cached review bundles.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the empty-cache guardrail.
**Verify:** Probed opt-in public live sources:
  GDELT returned HTTP 429 and Bybit returned HTTP 403 in this environment, both
  producing zero cache rows. The empty-cache bundle smoke now prints the warning
  and records it in README/manifest. `make verify` passes, including 226/226
  tests, alert render smoke, backtest fixture smoke, and paper scoreboard.
**Notes/risks:** This does not create real reviewed validation evidence. The
next validation step still requires at least one working research event source
or local event evidence feed.

## 2026-06-16 — Add event-discovery provider readiness report · Codex
**Why:** The configured-source review cycle can only build real validation rows
when at least one event source is enabled. On the current local config, no event
sources are ready, so the workflow needed a redacted preflight that catches
that state instead of letting an empty refresh look useful.
**Changes:**
- Added `crypto_rsi_scanner/event_provider_status.py` with a pure readiness
  report that separates event sources from enrichment and never prints secret
  values.
- Added `main.py --event-discovery-status` plus `make event-discovery-status`
  for human/agent preflight before configured-source cache refreshes.
- Reused the same readiness logic in scanner event-discovery guards, so
  enrichment-only configuration no longer counts as a valid event source.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the provider-status workflow.
**Verify:** `.venv/bin/python main.py --event-discovery-status` and `--json`
show the current local state with 0/11 event sources ready and no secret values.
`make -n event-discovery-status` expands to the expected CLI.
`main.py --event-discovery-refresh` now prints the no-source readiness message
instead of running an empty refresh. `make verify` passes, including 225/225
tests, alert render smoke, backtest fixture smoke, and paper scoreboard.
**Notes/risks:** This is still research-only workflow support. The current
machine has no configured event sources enabled; the next validation progress
requires enabling at least one research event source before running
`make event-fade-configured-review-cycle`.

## 2026-06-16 — Add configured event-fade review cycle · Codex
**Why:** The one-command review cycle was fixture-backed, which is correct for
deterministic smoke work but not enough for collecting real event-fade
validation candidates from configured research sources.
**Changes:**
- Added `make event-discovery-refresh-configured`, which runs
  `main.py --event-discovery-refresh` with only the configured cache directory
  and no fixture path injection.
- Added `make event-fade-configured-review-cycle`, which refreshes configured
  event-discovery sources and then writes the cache-backed manual review bundle.
- Documented the fixture-backed vs configured-source workflow distinction in
  `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`.
**Verify:** `make -n event-discovery-refresh-configured` and
`make -n event-fade-configured-review-cycle` confirm the configured path does
not inject fixture paths. `git diff --check` passes. `make verify` passes,
including 223/223 tests, alert render smoke, backtest fixture smoke, and paper
scoreboard.
**Notes/risks:** This is workflow-only and research-only. The configured cycle
may use opt-in live providers if enabled in the environment/`.env`, but it still
writes only the observational cache and review bundle artifacts; it does not
route alerts, open paper trades, or write live signal/outcome/paper tables.

## 2026-06-16 — Default event-fade price export to real kline cache · Codex
**Why:** The review-bundle auto-price workflow defaulted through the checked-in
fixture kline directory, which is correct for offline tests but wrong for real
validation samples. A real review cycle should use the research Binance
daily-kline fetch/cache path unless the operator explicitly asks for fixtures.
**Changes:**
- Changed Makefile event-fade price export/review-bundle targets so
  `--event-fade-price-fixture-dir` is only passed when
  `EVENT_FADE_PRICE_FIXTURE_DIR` is set.
- Kept fixture smoke support by documenting
  `EVENT_FADE_PRICE_FIXTURE_DIR=fixtures/event_discovery/outcome_klines`.
- Updated `AGENTS.md` and `research/event_discovery_design.md` with the default
  real-price-cache behavior and explicit fixture override.
**Verify:** `make -n event-fade-export-outcome-prices` omits the fixture dir by
default and includes it when `EVENT_FADE_PRICE_FIXTURE_DIR=fixtures/event_discovery/outcome_klines`;
`make -n event-fade-cache-review-bundle EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=1`
does the same for review bundles. `make verify` passes, including tests, alert
render smoke, backtest fixture smoke, and paper scoreboard.
**Notes/risks:** This only changes Makefile defaults and docs. Running the
price-export/review-bundle target with auto-price enabled may now fetch Binance
daily klines unless a fixture dir is supplied; it still writes only local review
artifacts and never routes alerts, opens paper trades, or writes live storage.

## 2026-06-16 — Auto-fill event-fade review bundle outcomes · Codex
**Why:** Building a useful event-fade review bundle still required a separate
price-fixture export before outcome fields could be filled. The validation plan
needs a low-friction loop where refreshed cache rows, prior labels, price
evidence, and outcome fields can land in one local review workspace.
**Changes:**
- Added `--event-fade-review-bundle-export-prices` for review-bundle commands;
  when no explicit price fixture is supplied, the bundle writes a local
  `outcome_prices.json` and fills trigger/event-time outcome fields from it.
- Reused the existing research-only Binance/fixture kline export path and kept
  output limited to the requested bundle directory.
- Added price-export provenance and counts to review-bundle manifests and
  README output.
- Added `EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES` to Makefile review-bundle and
  review-cycle targets.
- Added offline regression coverage using checked-in event-fade outcome kline
  fixtures.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the one-step price/export/outcome-fill workflow.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 223/223.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is artifact-only review workflow support. It can fetch
Binance daily klines only when explicitly requested without a fixture path; it
does not write live storage, route alerts, open paper trades, or change
event-fade scoring.

## 2026-06-16 — Let event-fade review bundles preserve prior labels · Codex
**Why:** The review-cycle workflow could refresh the event-discovery cache and
write a new review bundle, but preserving valid labels/outcomes from a prior
review still required a separate merge command. That made it too easy to hand a
reviewer a fresh bundle that forgot already reviewed work.
**Changes:**
- Added optional prior-reviewed-sample merging to
  `main.py --event-fade-review-bundle` and
  `main.py --event-fade-cache-review-bundle` via
  `--event-fade-review-bundle-reviewed`.
- Threaded merge counts, copied-field counts, evidence-changed rows, and skipped
  evidence-change details into the review-bundle manifest and README.
- Added `EVENT_FADE_REVIEW_BUNDLE_REVIEWED` to Makefile review-bundle and
  review-cycle targets so cache refresh + bundle export can preserve prior
  review work in one command.
- Added regression coverage proving a bundle can merge prior review
  status/labels/notes, fill local outcomes, reduce the review queue, and record
  merge provenance.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the refreshed workflow.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 222/222.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is artifact-only review workflow support. The merge still
uses evidence fingerprints and leaves changed-evidence rows unreviewed; it does
not alter live storage, alerts, paper trades, or event-fade scoring.

## 2026-06-16 — Report event-fade review merge evidence drift · Codex
**Why:** Evidence-drift protection blocked stale review labels/outcomes, but a
reviewer still needed to know which rows were skipped and why. Counts alone are
not enough when the next task is manually reconciling a validation sample.
**Changes:**
- Added `ValidationSampleEvidenceChange` details to
  `crypto_rsi_scanner/event_validation.py`, including asset, event,
  relationship, and changed evidence field names.
- Added `format_merge_evidence_changes()` and wired scanner merge/template-apply
  commands to print skipped rows when evidence changed.
- Added tests for direct merge evidence-change details, sidecar evidence-change
  details, and scanner output that names the changed field.
- Updated `AGENTS.md` and `research/event_discovery_design.md` with the more
  inspectable merge/apply behavior.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 221/221.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This remains artifact-only validation workflow support. It does
not alter event discovery, event-fade scoring, alert routing, live storage, or
paper trading.

## 2026-06-16 — Guard event-fade review merges against evidence drift · Codex
**Why:** Review labels and outcome fields are only valid for the evidence the
human actually reviewed. A regenerated validation sample could previously carry
old labels/outcomes forward by event/asset identity even if the source,
classifier, timing, or signal evidence changed.
**Changes:**
- Added validation-sample evidence fingerprints to
  `crypto_rsi_scanner/event_validation.py`; full sample merges now copy review
  fields only when the evidence fingerprint is unchanged.
- Kept compact review-template application separate, with a narrower evidence
  check against the sidecar fields it actually contains.
- Updated scanner merge/apply output to report evidence-changed matched rows.
- Added regression tests for unchanged merges, changed-evidence merge skips, and
  changed-evidence sidecar skips.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the new merge rule.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 220/220.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Evidence-changed rows intentionally remain unreviewed so they
return to the labeling queue. This is artifact-only validation hardening; it
does not change event discovery, event-fade scoring, alert routing, live
storage, or paper trading.

## 2026-06-16 — Block reviewed event-fade rows missing source timing · Codex
**Why:** Point-in-time validation can catch late source evidence, but a reviewed
row with no source timestamps at all was effectively unaudited. The validation
dataset must prove when evidence was knowable, especially before it contributes
to proxy/control coverage or promotion metrics.
**Changes:**
- Added `missing_source_timing_rows` to event-fade validation review metrics,
  reports, next-sample work, and review-bundle manifests.
- Added a labeling-queue category for reviewed rows that need source timing
  evidence or removal.
- Added regression coverage for missing source timing and tightened the
  promotion-ready fixture to assert zero missing source timing.
- Updated `AGENTS.md` and `research/event_discovery_design.md` with the new
  blocker and queue priority.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 218/218.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is review-evidence tightening only. It does not change
event discovery, event-fade scoring, alert routing, live storage, or paper
trading.

## 2026-06-16 — Apply point-in-time source checks to dated controls · Codex
**Why:** Reviewed direct/ambiguous negative controls could previously skip
source-timing checks because `NO_TRADE` rows had no review decision time. That
could let post-event articles inflate the validation control sample even though
the event was not actually knowable before its catalyst time.
**Changes:**
- Tightened `crypto_rsi_scanner/event_validation.py` so reviewed
  `SHORT_TRIGGERED` rows still use `trigger_observed_at` as the decision time,
  while other reviewed dated rows use `event_time`.
- Added a regression test proving a reviewed direct-beneficiary control with
  source evidence after event time is blocked and prioritized for
  point-in-time review.
- Updated `AGENTS.md` and `research/event_discovery_design.md` with the
  decision-time convention.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 217/217.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This tightens review/promotion evidence only. It does not
change event discovery, event-fade scoring, alert routing, live storage, or
paper trading.

## 2026-06-16 — Align event-fade cohort counts with reviewed evidence · Codex
**Why:** The validation report's top-level metrics required
`review_status=reviewed` plus a known `human_label`, but cohort tables still
counted any labeled row as reviewed. A half-edited sidecar could therefore
inflate cohort counts even while the top-level review correctly blocked
promotion.
**Changes:**
- Added a shared reviewed-evidence predicate in
  `crypto_rsi_scanner/event_validation.py`.
- Updated event-type, relationship, and BTC-risk cohort metrics to use the same
  reviewed-evidence rule as the top-level validation review.
- Added regression assertions so labeled-but-not-reviewed rows do not contribute
  to cohort reviewed or triggered counts.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 216/216.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This only tightens research-review metrics. It does not change
event-fade scoring, discovery, alert routing, live storage, or paper trading.

## 2026-06-16 — Add event-fade review-cycle make target · Codex
**Why:** The validation-sample workflow depends on refreshing the observational
event cache and then building a cache-backed review bundle from that same cache.
The Makefile let those steps use different cache dirs when `EVENT_DISCOVERY_CACHE_DIR`
was overridden, which could silently hand off stale or missing rows.
**Changes:**
- `make event-discovery-refresh` and `make event-discovery-binance-listen` now
  pass `EVENT_DISCOVERY_CACHE_DIR` through to `RSI_EVENT_DISCOVERY_CACHE_DIR`.
- Added `make event-fade-review-cycle`, which runs the fixture-backed cache
  refresh and cache-backed review-bundle export with the same cache directory.
- Updated Make help, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the review-cycle workflow.
**Verify:** `make event-fade-review-cycle EVENT_DISCOVERY_CACHE_DIR=/tmp/event_fade_cycle_cache EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=/tmp/event_fade_cycle_bundle EVENT_FADE_QUEUE_LIMIT=2`
wrote 17 cached candidate snapshots and a 17-row review bundle from the same
cache. `.venv/bin/python tests/test_indicators.py` passes 216/216. `make verify`
passes, including tests, alert render smoke, backtest fixture smoke, and paper
scoreboard.
**Notes/risks:** This remains research-only and artifact-only. The new target
uses checked-in fixtures by default, respects the configured cache dir, and does
not route alerts, write live storage, infer labels, or open paper trades.

## 2026-06-16 — Print validation review after sidecar apply · Codex
**Why:** The manual event-fade review loop wrote a reviewed sample after applying
the editable sidecar, but it still required a separate `--event-fade-review-sample`
run to see remaining blockers. That is an easy step to forget while building the
real reviewed validation dataset.
**Changes:**
- `main.py --event-fade-apply-review-template` now prints the resulting
  validation review report and next-sample work immediately after writing the
  reviewed sample.
- Updated scanner-level regression coverage for the apply command's self-audit
  output.
- Updated `main.py` usage text, `AGENTS.md`, and
  `research/event_discovery_design.md` to document the self-auditing apply step.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 216/216.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is output-only. It still writes only the requested reviewed
sample artifact and does not infer labels, write live storage, route alerts, or
open paper trades.

## 2026-06-16 — Add event-fade review bundle manifest · Codex
**Why:** Review bundles are now the main handoff artifact for building the
event-fade validation sample. They need a machine-readable provenance/counts
file so humans, Claude, and Codex can audit what bundle was generated without
parsing the README and reports by hand.
**Changes:**
- Added `manifest.json` to `--event-fade-review-bundle` and
  `--event-fade-cache-review-bundle` outputs.
- The manifest records generated time, source sample/cache path, bundle file
  names, row counts, queue counts, promotion blockers, next-sample work, and
  optional outcome-fill stats.
- Updated bundle README text, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to include the manifest as part of the
  review workspace contract.
- Extended sample-backed and cache-backed bundle tests to assert manifest
  presence and key source/count/outcome fields.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 216/216.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This remains artifact-only. The manifest is written only inside
the requested bundle directory and does not infer labels, route alerts, write
live storage, or open paper trades.

## 2026-06-16 — Add cache-backed event-fade review bundle · Codex
**Why:** The real event-fade validation loop should hand off the latest
point-in-time discovery cache for human review without requiring a separate
manual export-sample step first.
**Changes:**
- Added `main.py --event-fade-cache-review-bundle OUT_DIR`, which reads latest
  cached candidate snapshots from `RSI_EVENT_DISCOVERY_CACHE_DIR` and writes the
  same local review workspace as `--event-fade-review-bundle`.
- Refactored the review-bundle writer so sample-backed and cache-backed bundles
  share queue, packet, sidecar, report, README, and optional outcome-fill
  behavior.
- Added `make event-fade-cache-review-bundle` plus top-level usage/help text.
- Added an offline regression test that writes a temporary research cache and
  builds a cache-backed bundle with local outcome prices.
- Relaxed a date-sensitive auto-report fixture assertion for `TESTAI` after the
  fixture event moved from pre-event blowoff risk into triggered state.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 216/216.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This remains artifact-only. It reads the research cache and
writes only the requested bundle directory; it does not route alerts, write live
storage, open paper trades, or infer review labels.

## 2026-06-16 — Require explicit reviewed status for event-fade samples · Codex
**Why:** The validation reviewer counted any row with a `human_label` as
reviewed evidence. That made half-edited sidecars risky: a label without an
explicit review status could accidentally contribute to promotion metrics.
**Changes:**
- Tightened `crypto_rsi_scanner/event_validation.py` so review evidence requires
  both `review_status=reviewed` and a known `human_label`.
- Added review metrics, blockers, queue categories, and next-step text for
  labels missing review status, reviewed rows missing labels, and invalid label
  values.
- Updated queue/report/CLI wording to say status/labels/outcomes rather than
  labels/outcomes only.
- Added regression coverage for invalid labels, missing review status, and
  reviewed rows missing labels.
- Fixed a date-sensitive event-discovery fixture report test by pinning its
  lookback/horizon window.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the stricter reviewed-row definition.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 215/215.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Older samples still load, but rows with labels and no
`review_status=reviewed` no longer count as reviewed evidence. They now appear
in the labeling queue and promotion blockers.

## 2026-06-16 — Add event-fade validation next-step checklist · Codex
**Why:** The event-fade validation report listed blockers, but the next action
still had to be inferred by a human or the next agent. The remaining Pro-plan
work is sample building, so the report should say exactly which coverage,
outcome, or point-in-time rows need attention next.
**Changes:**
- Added `validation_review_next_steps()` and a `NEXT SAMPLE WORK` section to
  `crypto_rsi_scanner/event_validation.py`, translating review metrics into
  concrete sample-building actions.
- Updated `main.py --event-fade-review-sample` help text to mention next-sample
  work.
- Expanded validation tests to cover blocked/unlabeled samples, promotion-ready
  samples, and mixed post-decision source evidence.
- Fixed the event-discovery design note's labeling-queue priority list to
  include post-decision source review, and updated `AGENTS.md`/`ROADMAP.md`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 214/214.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is reporting-only. It does not auto-label rows, infer
promotion readiness, route alerts, write live storage, open paper trades, or
change event-fade scoring.

## 2026-06-16 — Harden event-fade point-in-time source audits · Codex
**Why:** The validation sample tracked earliest source timestamps, but a
multi-source event could still mix one pre-decision source with another
post-decision source. The Pro plan explicitly requires point-in-time evidence,
so reviewed samples need to expose and block this leakage risk.
**Changes:**
- Extended `crypto_rsi_scanner/event_discovery.py` validation rows with
  `raw_published_at`, `raw_fetched_at`, `published_at_max`, and
  `fetched_at_max` in addition to existing min timestamps.
- Added `post_decision_source_rows` to
  `crypto_rsi_scanner/event_validation.py`; review reports now count/block
  reviewed rows containing any source evidence after the decision time.
- The labeling queue now prioritizes reviewed rows that need post-decision
  source review, and review packets/templates show min/max/raw source timing.
- Added tests for raw timestamp export, clean reviewed samples, all-late
  evidence, and mixed early/late source evidence.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the source-leakage guardrail.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 214/214.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is an additive validation-sample/schema change under the
same v1 artifact family; older samples without max/raw timestamp fields still
load, but new exports are more auditable.

## 2026-06-16 — Add event-fade review bundle workspace · Codex
**Why:** The validation workflow had all the individual pieces, but building a
human-review workspace still required several commands in the right order. A
single bundle command makes the reviewed event dataset easier to assemble
without changing live behavior.
**Changes:**
- Added `main.py --event-fade-review-bundle SAMPLE OUT_DIR`, which writes a
  local review workspace with `validation_sample.jsonl`, optional
  `validation_sample_with_outcomes.jsonl`, `labeling_queue.txt`,
  `review_packet.md`, `review_template.csv`, `review_report.txt`, and
  `README.md`.
- Added optional `--event-fade-review-bundle-prices PRICES` to fill trigger and
  event-time baseline outcomes into the bundle-local sample copy.
- Added `make event-fade-review-bundle` and top-level usage text.
- Added an offline scanner regression test that verifies the bundle files and
  outcome-filled sample contents.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the review-bundle workflow and
  artifact-only guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 213/213.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard. `.venv/bin/python main.py --help` exposes the new
bundle command.
**Notes/risks:** The bundle does not infer labels, write live storage, route
alerts, open paper trades, or imply event-fade promotion. The actual validation
sample still needs human labels and real local price outcomes.

## 2026-06-16 — Add event-fade review sidecar workflow · Codex
**Why:** Review packets make candidate evidence readable, but a human still had
to edit the full validation export to apply labels. A compact sidecar makes
human labeling safer and easier while preserving the full sample artifact.
**Changes:**
- Added compact event-fade review-template rows in
  `crypto_rsi_scanner/event_validation.py`, with stable event/asset/relationship
  identity, queue context, suggested labels, source URLs, and editable
  review/outcome fields.
- Added `main.py --event-fade-export-review-template SAMPLE OUT` and
  `main.py --event-fade-apply-review-template SAMPLE TEMPLATE OUT`; both are
  artifact-only and never infer labels or touch live storage.
- Added `make event-fade-export-review-template` and
  `make event-fade-apply-review-template`, plus top-level usage text.
- Added offline tests for sidecar export/load/apply and scanner command paths.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the sidecar workflow and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 212/212.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard. `.venv/bin/python main.py --help` exposes the new
commands.
**Notes/risks:** The actual event-fade sample still needs human labels and real
local price outcomes before any promotion beyond local reports.

## 2026-06-16 — Add event-fade review packet export · Codex
**Why:** The validation sample now has queue/review metrics, but manual labeling
still required jumping between source evidence, classifier rationale, signal
fields, and outcome columns. A Markdown packet makes the reviewed event dataset
easier to build without changing live behavior.
**Changes:**
- Added `event_validation.format_review_packet()` to render prioritized
  validation rows with source URLs, raw titles, classifier evidence,
  signal/risk fields, trigger/event-time outcomes, and explicit human review
  fields.
- Added `main.py --event-fade-review-packet SAMPLE OUT` plus
  `make event-fade-review-packet`; the command writes only the requested
  Markdown artifact or stdout.
- Added offline tests for the pure formatter and scanner write path in
  `tests/test_indicators.py`.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  to document the packet workflow and artifact-only guardrail.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 210/210.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is a human-review workflow artifact only. It does not
auto-label rows, modify samples, write live storage, route alerts, open paper
trades, or imply event-fade promotion.

## 2026-06-16 — Add event-fade validation diversity and latency gates · Codex
**Why:** The event-fade promotion plan requires evidence across more than one
event type and market context, plus trigger-latency visibility. The reviewer
showed cohorts, but it did not block too-narrow samples or report how long
post-event confirmation took.
**Changes:**
- Extended `crypto_rsi_scanner/event_validation.py` with reviewed proxy
  event-type diversity, reviewed trigger BTC-risk-bucket diversity, and
  trigger-latency metrics.
- `--event-fade-review-sample` now reports average/median trigger latency,
  negative trigger-latency rows, proxy event-type coverage, and trigger BTC-risk
  bucket coverage.
- Promotion evidence is now blocked when a fully covered sample is still
  concentrated in too few proxy event types or too few BTC-risk buckets, or when
  reviewed triggers occur before their event time.
- Added regression tests in `tests/test_indicators.py` for the new diversity
  blockers and latency report fields.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document latency/diversity review
  gates.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 208/208.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** These are validation gates only. They do not promote
event-fade, write live storage, route alerts, or open paper trades.

## 2026-06-16 — Compare event-fade triggers to event-time shorts · Codex
**Why:** The event-fade plan explicitly requires proving that waiting for
post-event failure beats simply shorting at the event timestamp. The validation
sample could fill trigger outcomes, but it had no event-time baseline to make
that comparison reviewable.
**Changes:**
- Added additive validation-sample fields for event-time baseline entry price,
  MFE/MAE, and 24h/72h/7d post-event returns in
  `crypto_rsi_scanner/event_discovery.py`.
- Extended `crypto_rsi_scanner/event_validation.py` so
  `fill_validation_outcomes()` fills both confirmed-trigger outcomes and the
  event-time short baseline from local OHLCV candles.
- The validation review now reports event-time baseline 72h return,
  trigger-vs-baseline 72h edge, missing baseline fields, and blocks promotion
  evidence when reviewed triggers lack a baseline or fail to beat it.
- Updated validation labeling queues so triggered rows missing the event-time
  baseline stay prioritized for outcome filling.
- Expanded fixture prices and tests in `tests/test_indicators.py` to prove the
  trigger-vs-event-time comparison and scanner price-export path.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document the trigger/baseline
  validation workflow.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 207/207.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This remains artifact-only validation. It does not promote
event-fade alerts, write live storage, open paper trades, or approve routing.

## 2026-06-16 — Add event-fade validation cohort review metrics · Codex
**Why:** The event-fade plan requires proving whether the edge survives by
event type and market context, not just in aggregate. The validation reviewer
only reported top-line trigger/outcome metrics, so it could miss a sample whose
edge is concentrated in one event class or BTC risk bucket.
**Changes:**
- Extended `crypto_rsi_scanner/event_validation.py` with validation cohort
  summaries by event type, relationship type, and BTC risk-on bucket.
- The `--event-fade-review-sample` report now prints cohort rows with reviewed
  counts, proxy/control coverage, reviewed triggers, trigger precision, MFE/MAE,
  and 72h post-event return.
- Added tests in `tests/test_indicators.py` proving cohort calculations and
  formatted report output on the fixture validation sample.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document cohort evidence as
  research-only validation review output.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 207/207.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Cohorts are evidence only. They do not relax promotion
blockers, route alerts, write live storage, open paper trades, or approve
event-fade promotion automatically.

## 2026-06-16 — Auto-resolve live Coinalyze derivatives symbols · Codex
**Why:** Live Coinalyze derivatives enrichment still required hand-written
future-market symbols, which made the event radar harder to run on newly
discovered assets. The safer default is to resolve preferred Coinalyze perp
symbols from assets the discovery pipeline has already linked, while keeping
explicit symbols as the override path.
**Changes:**
- Extended `crypto_rsi_scanner/derivatives_providers/coinalyze.py` with
  `future-markets` symbol resolution. Explicit
  `RSI_EVENT_DISCOVERY_COINALYZE_SYMBOLS` still wins; otherwise the provider can
  select one preferred perp market per requested base asset.
- Moved discovery-asset loading ahead of derivatives enrichment in
  `crypto_rsi_scanner/event_discovery.py` so live Coinalyze can derive base
  symbols from resolved assets and aliases.
- Added `RSI_EVENT_DISCOVERY_COINALYZE_AUTO_SYMBOLS` config and `.env.example`
  documentation, wired through the scanner report path.
- Added offline tests for future-market resolution preference, automatic base
  symbol extraction from discovery assets, exchange-suffix symbols, zero-value
  snapshot preservation, and the live provider fail-soft path.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document the auto-symbol path as
  research-only enrichment.
**Verify:** `make verify` passes: 207/207 tests, alert render smoke, backtest
fixture smoke, and paper scoreboard.
**Notes/risks:** Live Coinalyze is still enrichment only. It cannot create
events, route alerts, write live signal/outcome/paper tables, or bypass the
event-fade proxy/direct eligibility gate.

## 2026-06-16 — Add opt-in live Coinalyze derivatives enrichment · Codex
**Why:** The event-fade plan depends on derivatives crowding evidence, but
Coinalyze enrichment was fixture-only. Research radar runs need an opt-in live
path for OI/funding/crowding snapshots without turning derivatives into event
eligibility or live routing.
**Changes:**
- Extended `crypto_rsi_scanner/derivatives_providers/coinalyze.py` with an
  opt-in live REST path using configured Coinalyze symbols and API key. It
  fetches current OI/funding plus OI history, liquidations, long/short ratio,
  and futures volume history over a configurable lookback.
- Preserved legitimate zero values in the derivatives snapshot mapper and fixed
  Coinalyze exchange-suffix symbols such as `TESTUSDT_PERP.A` so they key by
  base asset correctly.
- Added `RSI_EVENT_DISCOVERY_COINALYZE_*` config and `.env.example` settings,
  wired through `event_discovery.py` and `scanner.py`.
- Added offline tests for documented Coinalyze current/history response shapes,
  symbol batching headers/params, missing-config fail-soft behavior, and live
  snapshot field derivation.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document live Coinalyze as
  research-only enrichment.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 205/205.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Live Coinalyze requires explicit symbols such as
`BTCUSDT_PERP.A`; it does not discover events by itself and must not bypass the
proxy/direct event-fade eligibility gate.

## 2026-06-16 — Add raw Binance announcement cache listener · Codex
**Why:** Binance announcements are a push WebSocket feed, so report/refresh
bounded fetches can miss source evidence between runs. The event-discovery plan
needs point-in-time raw event evidence preserved before any classification or
promotion work.
**Changes:**
- Added `main.py --event-discovery-binance-listen`, which uses the configured
  signed Binance CMS WebSocket provider and appends raw announcement evidence to
  the existing research-only JSONL cache.
- Added `make event-discovery-binance-listen` and documented the command in
  `main.py`, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`.
- The listener writes only `raw_events.jsonl` and `discovery_runs.jsonl` rows
  via the existing cache writer. It does not normalize events, route alerts,
  write live SQLite signal/outcome/paper tables, or open paper trades.
- Added a scanner-level regression test that stubs the Binance provider and
  verifies raw cache rows plus run metadata are written.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 203/203.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Continuous collection still needs an ops wrapper such as a
LaunchAgent/KeepAlive job. This command is the safe research capture primitive,
not a trading promotion.

## 2026-06-16 — Add opt-in live Binance announcement discovery · Codex
**Why:** The radar could parse captured Binance CMS announcement payloads, but
it still could not ingest Binance's official signed WebSocket feed during
research refresh/report runs. The Pro-plan exchange-provider phase calls for
automatic discovery from exchange announcements while preserving the proxy gate.
**Changes:**
- Extended `crypto_rsi_scanner/event_providers/binance_announcements.py` with an
  opt-in bounded live WebSocket fetch path for Binance CMS announcements. It
  signs the `com_announcement_en` subscription URL, uses the API key header,
  listens for a configurable short window, and reuses the same CMS DATA parser
  as fixtures.
- Added config and `.env.example` knobs for live Binance announcement research:
  API key/secret, WebSocket URL, topic, recv window, listen seconds, and max
  messages.
- Wired the live Binance source through `event_discovery.py` and `scanner.py`,
  including source-detection for report/refresh commands.
- Added offline WebSocket tests covering signed URL/header construction, control
  frame tolerance, CMS DATA parsing, and missing-credential fail-soft behavior.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to document the signed, opt-in,
  research-only Binance path and keep always-on caching as future work.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 202/202.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is a bounded report/refresh fetch, not an always-on
listener. Binance listing/perp announcements remain direct events and stay
`NO_TRADE` under the event-fade proxy gate unless another source proves a true
proxy relationship.

## 2026-06-16 — Add opt-in live CoinGecko discovery universe · Codex
**Why:** Event discovery had live news/exchange inputs, but asset resolution
still depended on local universe fixtures. Live research passes need the same
clean CoinGecko universe hygiene used by the scanner, without making the
universe itself an event source or promoting event-fade output.
**Changes:**
- Added `RSI_EVENT_DISCOVERY_UNIVERSE_LIVE` and
  `RSI_EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT` config/env examples, wired through
  `scanner.py` and `event_discovery.run_manual_discovery()`.
- Extended `crypto_rsi_scanner/event_providers/coingecko_universe.py` so it can
  optionally fetch live top markets through the existing `CoinGeckoClient`, apply
  `universe.filter_markets_with_audit`, and fail soft on provider errors.
- Added offline tests with injected fake CoinGecko clients for live fetch,
  hygiene filtering, overfetch limits, and fail-soft behavior.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to mark live CoinGecko as resolver
  enrichment only: research-only, opt-in, no alert routing, no live DB writes,
  no paper trades.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 200/200.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Enabling `RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1` alone does not
create radar events; another event source or fixture must be configured.

## 2026-06-16 — Parse Binance CMS announcement payloads · Codex
**Why:** Binance's official English announcement stream publishes CMS WebSocket
`DATA` messages where the announcement content is a JSON string inside the
`data` field. The existing Binance fixture parser only handled already-flattened
announcement rows, so captured official payloads could not feed the
event-discovery radar.
**Changes:**
- Extended `crypto_rsi_scanner/event_providers/_announcement_common.py` to unwrap
  Binance CMS `DATA` messages, preserve `topic`/`message_type`, parse
  `publishDate` timestamps, and feed the nested announcement through the same
  direct listing/perp classification path as other announcement fixtures.
- Added a regression test using the official `com_announcement_en` payload shape
  with stringified `data`.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` to record captured Binance CMS payload
  support and keep the boundary clear: a true live Binance WebSocket
  listener/cache adapter is still future work.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 198/198.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This is parser support for official captured payloads, not a
new live listener. It preserves the research-only event-discovery boundary and
does not route alerts, write live signal/outcome/paper tables, or promote
event-fade signals.

## 2026-06-16 — Add opt-in live CryptoPanic discovery · Codex
**Why:** The event-fade validation pipeline needs more real news coverage for
proxy/direct/ambiguous narrative review. CryptoPanic was fixture-only; an
explicit, token-gated live path can feed research reports and cache exports
without changing live alert behavior.
**Changes:**
- Extended `crypto_rsi_scanner/event_providers/cryptopanic.py` from
  fixture-only to optional live posts fetching with API-token config, public/
  filter/currency/region/kind/search parameters, injected opener support, and
  fail-soft behavior.
- Wired `RSI_EVENT_DISCOVERY_CRYPTOPANIC_*` config through `config.py`,
  `event_discovery.py`, and `scanner.py`; scanner no-source messages now refer
  to generic live research providers instead of only Bybit.
- Added `.env.example` entries for the CryptoPanic live path.
- Added offline tests for request parameters, response parsing, missing-token
  behavior, and fetch failure handling.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  to record CryptoPanic as an opt-in live research source.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 197/197.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Live CryptoPanic fetching is opt-in and requires
`RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN`. It feeds local reports/cache/export
paths only; it does not route Telegram alerts, write live signal/outcome/paper
tables, open paper trades, or promote event-fade signals.

## 2026-06-16 — Add opt-in live project-blog RSS discovery · Codex
**Why:** The event-fade validation sample needs broader real narrative coverage,
especially project-sourced posts that may announce synthetic/proxy exposure or
dated catalysts. RSS/Atom feeds are a no-key source that can safely feed the
research-only event radar.
**Changes:**
- Extended `crypto_rsi_scanner/event_providers/project_blog_rss.py` from
  fixture-only to optional live RSS/Atom fetching from explicit feed URLs, with
  injected opener support, deterministic fetched timestamps for tests, and
  fail-soft per-feed behavior.
- Added RSS item and Atom entry parsing into the existing news-row pipeline so
  live feed entries reuse the same event-type inference, point-in-time
  timestamps, and proxy/direct no-trade safety rules as fixtures.
- Added RFC 2822/RSS date parsing in
  `crypto_rsi_scanner/event_providers/_news_common.py`.
- Wired `RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE`,
  `RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS`, and timeout config through
  `config.py`, `event_discovery.py`, and `scanner.py`.
- Updated `.env.example`, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`; cleaned inline comments from
  `.env.example` value lines so copying the file cannot create invalid env
  values under the repo's minimal dotenv loader.
- Added offline tests for RSS and Atom parsing, RFC date handling, request
  timeout/headers, and fail-soft feed errors.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 196/196.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** Live RSS is opt-in and research-only. It only feeds local
reports/cache/export paths and does not route Telegram alerts, write live
signal/outcome/paper tables, open paper trades, or promote event-fade signals.

## 2026-06-16 — Add opt-in live GDELT event discovery · Codex
**Why:** The event-fade validation pipeline needs more real narrative/event
coverage, but live discovery sources must remain research-only and fail-soft.
GDELT is a useful no-key news source for proxy-catalyst radar coverage.
**Changes:**
- Extended `crypto_rsi_scanner/event_providers/gdelt.py` from fixture-only to
  optional live GDELT Article List JSON fetching with request-time bounds,
  configurable query/max-records/timeout, injected opener support for tests,
  and fail-soft behavior.
- Added shared news-row conversion and compact `YYYYMMDDHHMMSS` timestamp
  parsing in `crypto_rsi_scanner/event_providers/_news_common.py`.
- Wired `RSI_EVENT_DISCOVERY_GDELT_LIVE`, query, max-record, timeout, and base
  URL settings through `config.py`, `event_discovery.py`, and `scanner.py`.
- Added offline provider regression coverage for GDELT request parameters,
  compact timestamp parsing, empty responses, and fetch failures.
- Updated `.env.example`, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`; also moved live-provider comments in
  `.env.example` off value lines so the minimal dotenv loader cannot treat them
  as truthy values.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 195/195.
`make verify` passes, including tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** GDELT live fetching is opt-in and research-only. It feeds local
reports/cache/export paths only; it does not route Telegram alerts, write live
signal/outcome/paper tables, open paper trades, or promote event-fade signals.

## 2026-06-16 — Export validation price fixtures from sample rows · Codex
**Why:** Outcome filling could consume local price JSON, but building that JSON
still required hand-writing candles. The validation workflow needs a
research-only path from a sample's triggered rows to local OHLCV fixtures before
human review.
**Changes:**
- Added `crypto_rsi_scanner/event_price_history.py` to export local
  `event_fade_outcome_prices_v1` JSON for `SHORT_TRIGGERED` validation rows,
  using either Binance-style fixture CSVs or the existing cached Binance kline
  fetch path.
- Added `main.py --event-fade-export-outcome-prices SAMPLE OUT`, optional
  fixture/price-days/cache-refresh flags, and
  `make event-fade-export-outcome-prices`.
- Extended shared Binance kline DataFrames with `high` and `low`, and taught
  fixture CSV loading to preserve optional `high`, `low`, and `quote_volume`.
- Added checked-in offline kline fixture
  `fixtures/event_discovery/outcome_klines/TESTVELVETUSDT.csv`.
- Added tests for high/low kline preservation, pure price-fixture export,
  scanner CLI export, and export-prices → fill-outcomes integration.
- Updated `AGENTS.md`, `ROADMAP.md`, `main.py`, and
  `research/event_discovery_design.md` with the price-export workflow.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 194/194.
Offline workflow smoke passes:
`make event-fade-export-sample` → `make event-fade-export-outcome-prices` →
`make event-fade-fill-outcomes` → `make event-fade-labeling-queue` →
`make event-fade-review-sample`. Generated price export reports
`assets=1/1` and `price_rows=4`.
**Notes/risks:** The new export command is research-only and artifact-only. It
may fetch Binance daily klines only when run without a fixture directory; it
does not write live scanner storage, route alerts, open paper trades, or imply
event-fade promotion.

## 2026-06-16 — Add validation outcome filling from local prices · Codex
**Why:** Event-fade validation samples had blank outcome fields, and the review
tool correctly blocked reviewed triggered rows without MFE/MAE and 72h
post-event returns. The workflow needed an artifact-only way to fill those
fields from local price histories before human review.
**Changes:**
- Added `event_validation.load_outcome_price_fixture()` and
  `fill_validation_outcomes()` to fill `SHORT_TRIGGERED` sample rows from local
  OHLCV candles while preserving existing fields unless overwrite is requested.
- Added `main.py --event-fade-fill-outcomes SAMPLE PRICES OUT` plus
  `make event-fade-fill-outcomes`.
- Added `fixtures/event_discovery/outcome_prices.json` for offline regression
  coverage of the TESTVELVET short outcome path.
- Added tests for outcome math, skipped-existing behavior, labeling-queue
  interaction, and scanner CLI file output.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the outcome-fill workflow.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 192/192.
Offline workflow smoke passes:
`make event-fade-export-sample` → `make event-fade-fill-outcomes` →
`make event-fade-labeling-queue` → `make event-fade-review-sample`. After
filling, the triggered row only needs `human_label`; the review remains blocked
on missing human labels/sample coverage.
**Notes/risks:** This is artifact-only validation tooling. It writes only the
requested output sample and does not write live SQLite signal/outcome/paper
tables, send notifications, open paper trades, or imply promotion.

## 2026-06-16 — Export validation samples from event-discovery cache · Codex
**Why:** The event-fade validation workflow could write point-in-time cache
snapshots, but review artifacts still had to be generated from the current
discovery run. Cached live/refreshed observations need a direct path into the
same human-review sample schema.
**Changes:**
- Added `event_cache.load_cached_validation_sample()` to unwrap
  `candidate_snapshots.jsonl` into normal `event_fade_validation_sample_v1`
  rows and keep only the latest snapshot per event/asset/relationship identity
  by default.
- Added `main.py --event-fade-export-cache-sample PATH` and
  `make event-fade-export-cache-sample` to export cached snapshots as JSONL/CSV
  validation samples.
- Added regression tests for cache snapshot unwrapping, latest-row dedupe, and
  scanner CLI export from a refreshed temp cache.
- Updated `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and
  `research/event_discovery_design.md` with the cached-sample workflow and
  research-only guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 190/190.
Temp-cache workflow smoke passes:
`make event-discovery-refresh` → `make event-fade-export-cache-sample` →
`make event-fade-review-sample`, with the review correctly blocked because rows
are not human-labeled yet.
**Notes/risks:** This only writes the requested local sample artifact. It does
not write live SQLite signal/outcome/paper tables, send notifications, open
paper trades, or imply event-fade promotion.

## 2026-06-16 — Add event-discovery JSONL cache refresh · Codex
**Why:** Live/refreshed event sources need point-in-time preservation before
they can support manual validation or backtests. `RSI_EVENT_DISCOVERY_CACHE_DIR`
already existed and was gitignored, but nothing wrote the observational cache.
**Changes:**
- Added `crypto_rsi_scanner/event_cache.py`, a research-only JSONL cache writer
  for raw events, normalized events, asset links, classifications, candidate
  snapshots, and discovery-run metadata.
- Added `main.py --event-discovery-refresh` and
  `make event-discovery-refresh`, wired through the existing discovery source
  configuration and `RSI_EVENT_DISCOVERY_CACHE_DIR`.
- Candidate snapshots reuse the validation-sample row builder so cache exports
  and human-review exports stay aligned.
- Added offline tests for cache artifact contents, point-in-time timestamps,
  dedupe of stable evidence rows, candidate snapshot appends, and scanner CLI
  cache refresh output.
- Updated `.env.example`, `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and
  `research/event_discovery_design.md` with the cache workflow and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 189/189.
`RSI_EVENT_DISCOVERY_CACHE_DIR=$(mktemp -d)/cache make event-discovery-refresh`
writes the expected research cache summary. `git diff --check` passes.
`make verify` passes.
**Notes/risks:** This is observational research storage only. It writes JSONL
artifacts under the configured cache directory, not live SQLite signal/outcome/
paper tables, notifications, paper trades, or execution paths.

## 2026-06-16 — Add opt-in live Bybit announcement discovery · Codex
**Why:** The Pro plan's event radar should eventually discover exchange events
automatically, but the repo only had fixture-backed announcement parsing. Bybit
has an official unauthenticated announcements endpoint that can be used as a
safe first live source for research-only radar/export runs.
**Changes:**
- Extended the Bybit announcement provider with explicit opt-in live fetching
  from `GET /v5/announcements/index`, while keeping fixture mode as the default.
- Added Bybit live config knobs:
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE`,
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_BASE_URL`,
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LOCALE`,
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TYPE`,
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIMIT`, and
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_TIMEOUT`.
- Taught the shared announcement parser to understand Bybit's documented
  `dateTimestamp`, `startDateTimestamp`, and `startDataTimestamp` fields.
- Wired the opt-in live provider through discovery reports/exports, updated
  `.env.example`, `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md`.
- Added an offline fake-HTTP regression test for the documented Bybit response
  shape, URL construction, timestamp parsing, listing normalization, and
  fail-soft behavior.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 187/187.
An opt-in live smoke with `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE=1`
exits cleanly and prints an empty report after Bybit returns HTTP 403 in this
environment. `git diff --check` passes. `make verify` passes.
**Notes/risks:** Live Bybit fetch is default-off and research-only. Bybit
listings/perp listings are direct exchange events and remain `NO_TRADE` unless
separate evidence proves a true proxy relationship.

## 2026-06-16 — Add event-fade validation labeling queue · Codex
**Why:** The event-fade validation workflow could export, merge, and review
samples, but it did not tell a reviewer which rows to label next or which
triggered rows were missing required outcome fields.
**Changes:**
- Added `event_validation.build_labeling_queue()` and
  `format_labeling_queue()` to prioritize unknown labels, point-in-time issues,
  unlabeled triggered rows, triggered rows missing required outcomes, proxy
  candidates, and direct/ambiguous controls.
- Added `main.py --event-fade-labeling-queue PATH` plus
  `make event-fade-labeling-queue`, controlled by `EVENT_FADE_SAMPLE_IN` and
  `EVENT_FADE_QUEUE_LIMIT`.
- Added offline tests for pure queue priority, reviewed-trigger outcome gaps,
  and scanner CLI output.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the queue command and artifact-only
  guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 186/186.
`make event-fade-export-sample ... && make event-fade-labeling-queue ...`
prints the expected prioritized queue. `git diff --check` passes.
`make verify` passes.
**Notes/risks:** This is a read-only sample review aid. It does not auto-label
rows, write live storage, route alerts, open paper trades, or imply promotion.

## 2026-06-16 — Add event-fade validation sample merge workflow · Codex
**Why:** A reviewed validation sample will need repeated fresh exports as event
fixtures expand, and prior human labels/outcomes should not be lost or manually
retyped.
**Changes:**
- Added `event_validation.merge_review_fields()` to copy nonblank review fields
  from a previously labeled sample into a fresh export by event/asset/
  relationship identity.
- Added `main.py --event-fade-merge-sample FRESH REVIEWED OUT` and
  `make event-fade-merge-sample`, with separate fresh/reviewed/merged path
  variables.
- Added offline tests for direct merge behavior and scanner CLI file output.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the export → merge → label → review
  workflow and artifact-only guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 183/183.
`git diff --check` passes. `make verify` passes.
**Notes/risks:** Merge copies only nonblank human review/outcome fields and only
writes the requested output artifact. It does not write live storage, route
alerts, open paper trades, or imply execution.

## 2026-06-16 — Harden event-fade validation promotion blockers · Codex
**Why:** The review command summarized labels/outcomes, but it could still mark
a tiny or point-in-time-invalid sample as ready if thresholds were lowered. The
Pro plan explicitly requires point-in-time correctness and stronger evidence
before any promotion discussion.
**Changes:**
- Strengthened `event_validation.review_validation_sample()` with default
  blockers for fewer than 10 reviewed `SHORT_TRIGGERED` rows, trigger precision
  below 60%, MFE/MAE below 1.5, and source evidence first seen after the
  decision time.
- The review report now prints reviewed trigger minimums, minimum precision,
  point-in-time violation counts, and minimum MFE/MAE.
- Added a regression test proving a bad labeled trigger is blocked for late
  evidence, false-positive label, weak MFE/MAE, and unfavorable 72h short
  return.
- Updated `AGENTS.md` and `research/event_discovery_design.md` with the stricter
  review criteria.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 181/181.
`git diff --check` passes. `make verify` passes.
**Notes/risks:** This still only affects local validation review. It does not
route alerts, write live storage, open paper trades, or imply execution.

## 2026-06-16 — Add event-fade validation review metrics · Codex
**Why:** The validation exporter produced review artifacts, but the plan also
needs a way to evaluate labeled samples against promotion criteria before any
alert or paper-trading discussion.
**Changes:**
- Added `crypto_rsi_scanner/event_validation.py` to load JSONL/CSV validation
  samples, summarize labels/outcomes, compute trigger precision, false-positive
  rate, MFE/MAE, post-event returns, and emit conservative promotion blockers.
- Added `main.py --event-fade-review-sample PATH` and
  `make event-fade-review-sample`; the Make target reads
  `EVENT_FADE_SAMPLE_IN` so hand-labeled files are not overwritten by export.
- Added offline tests for unlabeled exports, labeled metric summaries, JSONL/CSV
  loading, and scanner CLI plumbing.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the export → label → review workflow
  and the non-promotion guardrail.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 180/180.
`make event-fade-export-sample && make event-fade-review-sample` reads the
17-row blank export and correctly prints `BLOCKED` for missing reviewed proxy,
control, and triggered samples. `git diff --check` passes. `make verify` passes.
**Notes/risks:** The reviewer is evidence only. Even a clean report says
`READY FOR HUMAN DECISION`; it does not change routing, storage, paper trading,
or execution behavior.

## 2026-06-16 — Add event-fade validation sample export · Codex
**Why:** Phase 10 needed a concrete review artifact so discovered event-fade
candidates can become a manually labeled validation sample without promoting
the research sleeve into alerts, paper trades, DB writes, or execution.
**Changes:**
- Added a versioned event-fade validation sample schema in
  `crypto_rsi_scanner/event_discovery.py` with JSONL/CSV serializers and a
  writer.
- Export rows now preserve raw source ids/providers/titles/content hashes,
  point-in-time event/source timestamps, source URLs, asset-link evidence,
  proxy/direct classification evidence, fade state/signal, component scores,
  feature fields, missing-data markers, and blank human-review/outcome columns.
- Added `main.py --event-fade-export-sample PATH`; `.csv` writes CSV, other
  suffixes write JSONL, and `-` prints JSONL to stdout.
- Added `make event-fade-export-sample`, defaulting to
  `/tmp/event_fade_validation_sample.jsonl`, using the full offline discovery
  fixture stack.
- Added offline tests for validation rows, JSONL/CSV serialization, file
  writing, and scanner CLI plumbing.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with Phase 10 status and the remaining
  human-labeling boundary.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 177/177.
`make event-fade-export-sample` writes 17 rows to
`/tmp/event_fade_validation_sample.jsonl`. `git diff --check` passes.
`make verify` passes.
**Notes/risks:** This is still fixture-backed and local-only. The exporter writes
only the requested artifact; it does not write live signal/outcome/paper tables,
send Telegram alerts, open paper trades, or imply execution. The next real step
is expanding the reviewed sample and filling human labels/outcomes.

## 2026-06-16 — Add grouped event-fade auto report · Codex
**Why:** The discovery pipeline had a flat radar/classification report, but the
Phase 9 work order called for a clearer event-fade output grouped by candidate
lifecycle before building the validation sample.
**Changes:**
- Added `event_discovery.format_event_fade_auto_report()` with EVENT RADAR,
  PROXY WATCHLIST, BLOWOFF RISK, EVENT PASSED, ARMED, TRIGGERED,
  REJECTED / NO TRADE, and AMBIGUOUS sections.
- Candidate rows now surface symbol/coin id, event timing, first-seen time,
  link/classifier confidence, relationship type, fade score, state/signal,
  missing data, reason codes, warnings, source URLs, and invalidation when
  available.
- Added `main.py --event-fade-auto-report` and `make event-fade-auto-report`;
  both reuse the existing fixture-only discovery inputs and do not write DB
  rows, send notifications, open paper trades, or imply execution.
- Shared scanner discovery fixture loading between the flat radar report and the
  grouped auto report so provider wiring cannot drift.
- Made Makefile discovery fixture reports deterministic with a 120-hour
  lookback and 2-day horizon.
- Expanded offline tests for grouped section output and scanner CLI plumbing.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with Phase 9 status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 175/175.
`make event-fade-auto-report` prints the grouped research-only report with
TESTVELVET under TRIGGERED, TESTAI under BLOWOFF RISK, TESTPRED under PROXY
WATCHLIST, direct cases under REJECTED / NO TRADE, and ambiguous cases under
AMBIGUOUS. `git diff --check` passes. `make verify` passes.
**Notes/risks:** Still fixture-backed and local-only. This is a reporting
surface for validation work, not a live routing, paper-trading, storage, or
execution path.

## 2026-06-16 — Add fixture supply/on-chain enrichment for event discovery · Codex
**Why:** The event-fade radar needs local supply and on-chain pressure evidence
before validation-sample work, but those fields must remain research-only
evidence and must not bypass the proxy/direct hard gate.
**Changes:**
- Added fixture-backed Tokenomist-, Etherscan-, Arkham-, and Dune-style supply
  providers under `supply_providers/`.
- Added optional config/report paths:
  `RSI_EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH`,
  `RSI_EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH`,
  `RSI_EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH`, and
  `RSI_EVENT_DISCOVERY_DUNE_SUPPLY_PATH`.
- Wired supply snapshots into `event_discovery.run_manual_discovery()`,
  `main.py --event-discovery-report`, and `make event-discovery-report`; the
  report now prints `supply=yes/no` alongside derivatives coverage.
- Added fixtures covering unlock pressure, CEX inflow, team/MM wallet activity,
  holder concentration, admin/mint risk, and a conflicting TESTVELVET provider
  row that proves raw event fixture supply evidence wins.
- Expanded offline tests for supply fixture parsing, malformed fixture fail-soft
  behavior, supply enrichment, raw-evidence precedence, scanner report wiring,
  direct/non-proxy safety, and preserving explicit `0` / `False` supply values.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with Phase 8 status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 173/173.
`make event-discovery-report` prints 20 raw events / 19 normalized events and
shows supply-enriched TESTLIST/TESTUNLOCK/TESTAI/TESTPRED/TESTFAN candidates
while direct listing/unlock cases remain `NO_TRADE`. `git diff --check` passes.
`make verify` passes.
**Notes/risks:** Providers remain fixture-backed only. No live Tokenomist,
Etherscan, Arkham, Dune, cache, DB, notification, paper-trading, or execution
path was added.

## 2026-06-16 — Add fixture external catalyst providers · Codex
**Why:** The event-fade radar needs external catalysts outside crypto, such as
IPO calendars, sports fixtures, and prediction markets, but those sources must
stay radar-first and must not create candidates without crypto asset evidence.
Phase 7 adds that fixture-only layer.
**Changes:**
- Added fixture-backed external IPO, sports-fixture, and prediction-market event
  providers over a shared external-catalyst parser.
- Added optional config/report paths:
  `RSI_EVENT_DISCOVERY_EXTERNAL_IPO_PATH`,
  `RSI_EVENT_DISCOVERY_SPORTS_FIXTURES_PATH`, and
  `RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH`.
- Added fixtures for a SpaceX IPO date-only radar event, a clean Test FC sports
  fixture, a linked TESTFAN sports proxy fixture, a linked TESTPRED/OpenAI
  prediction-market catalyst, and an election prediction market with no crypto
  asset evidence.
- Expanded aliases for TESTPRED and wired the external fixtures into
  `make event-discovery-report`.
- Added offline tests for provider parsing, malformed fixture fail-soft
  behavior, external-only radar/no-candidate safety, linked proxy candidates,
  date-only event-time confidence, and scanner report wiring.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with Phase 7 status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 170/170.
`make event-discovery-report` prints external IPO/sports/prediction events while
external-only rows remain radar-only and linked rows stay non-executing local
report candidates. `git diff --check` passes. `make verify` passes.
**Notes/risks:** Providers remain fixture-backed only. No live IPO, sports,
prediction-market, cache, DB, notification, paper-trading, or execution path was
added.

## 2026-06-16 — Add fixture news/proxy narrative discovery · Codex
**Why:** The event-fade radar needs narrative/news sources to discover
VELVET-style proxy setups, not only structured crypto calendars and exchange
announcements. Phase 6 adds offline news fixtures while preserving the
research-only/no-routing boundary.
**Changes:**
- Added fixture-backed CryptoPanic-, GDELT-, and project-blog/RSS-style news
  providers over a shared news parser that accepts common API-like shapes such
  as `results`, `features`, and `items`.
- Added optional config/report paths:
  `RSI_EVENT_DISCOVERY_CRYPTOPANIC_PATH`, `RSI_EVENT_DISCOVERY_GDELT_PATH`, and
  `RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH`.
- Added fixtures for TESTAI/OpenAI proxy exposure, TESTBTC/BTC ETF direct
  beneficiary news, TESTFAN sports/fan-token proxy attention, TESTLATE
  post-event proxy evidence, and TESTAMBIG ambiguous momentum news.
- Expanded aliases for the new news fixture assets.
- Tightened deterministic classification so `etf_approval` and `etf_launch`
  event types classify as direct token events even when article wording is not
  exactly "ETF approval".
- Expanded offline tests for news provider parsing, malformed fixture fail-soft
  behavior, proxy/direct/ambiguous classification, post-event first-seen safety,
  deterministic fixed-time trigger behavior, and scanner report wiring.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with Phase 6 status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 167/167.
`make event-discovery-report` prints 15 raw events / 14 normalized events with
TESTAI, TESTFAN, TESTLATE, and TESTAMBIG included; direct/ambiguous/late cases
remain `NO_TRADE`. `git diff --check` passes. `make verify` passes.
**Notes/risks:** Providers remain fixture-backed only. No live CryptoPanic,
GDELT, RSS, cache, DB, notification, paper-trading, or execution path was added.

## 2026-06-16 — Add fixture derivatives enrichment for event discovery · Codex
**Why:** Event-fade validation needs crowding evidence, not just dated events.
Phase 5 adds local Coinalyze-style derivatives snapshots so the research radar
can score OI/funding/perp crowding while staying offline and alert-only.
**Changes:**
- Added `derivatives_providers/` with a fixture-backed
  `CoinalyzeDerivativesProvider` for OI, funding, futures volume,
  perp/spot-volume ratio, liquidations, long/short ratio, and basis snapshots.
- Added `RSI_EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH` and wired optional
  derivatives enrichment through `event_discovery.run_manual_discovery()` and
  `main.py --event-discovery-report`.
- Added `fixtures/event_discovery/coinalyze_derivatives.json` covering high
  TESTLIST crowding, TESTPERP no-perp availability, and a conflicting
  TESTVELVET row that proves raw event fixture derivatives take precedence.
- The discovery report now prints candidate fade score and `deriv=yes/no` so
  enrichment is visible from local reports.
- Hardened derivatives symbol normalization so coin symbols ending in `PERP`
  are not over-stripped into false resolver keys.
- Expanded offline tests for derivatives fixture parsing, malformed fixture
  fail-soft behavior, candidate enrichment, raw-snapshot precedence, direct
  listing/no-trade safety under high crowding, and scanner report plumbing.
- Updated `AGENTS.md`, `ROADMAP.md`, and
  `research/event_discovery_design.md` with the Phase 5 status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 164/164.
`make event-discovery-report` prints TESTLIST and TESTPERP with `deriv=yes` but
both still `NO_TRADE/DISCOVERED`; TESTVELVET remains the only proxy trigger
fixture. `git diff --check` passes. `make verify` passes.
**Notes/risks:** This is still fixture-backed research tooling only. No live
Coinalyze calls, cache writes, live DB writes, notifications, paper trades, or
execution were added.

## 2026-06-16 — Add fixture structured calendar and unlock providers · Codex
**Why:** The event-fade validation sample needs more dated direct/control
events, including crypto calendar catalysts and supply unlocks, before any proxy
fade result can be trusted. Phase 4 adds those sources as offline fixtures only.
**Changes:**
- Added fixture-backed `CoinMarketCalProvider` for structured dated crypto
  calendar events and `TokenomistProvider` for token unlock events.
- Added `fixtures/event_discovery/coinmarketcal_events.json` and
  `fixtures/event_discovery/tokenomist_unlocks.json`, plus TESTCAL and
  TESTUNLOCK alias rows.
- Wired optional config/report paths:
  `RSI_EVENT_DISCOVERY_COINMARKETCAL_PATH` and
  `RSI_EVENT_DISCOVERY_TOKENOMIST_PATH`.
- Tokenomist unlock fixtures now populate `supply.unlock_amount` and
  `supply.unlock_pct_circulating` on the generated `FadeCandidate`, while still
  classifying as direct unlocks that remain `NO_TRADE`.
- Expanded offline tests for structured provider parsing, malformed fixture
  fail-soft behavior, structured-only scanner reports, direct/no-trade calendar
  behavior, and unlock supply enrichment.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the Phase 4 structured calendar/unlock status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 161/161.
`make event-discovery-report` prints TESTCAL as direct protocol upgrade and
TESTUNLOCK as direct unlock, both `NO_TRADE/DISCOVERED`. `make verify` passes.
**Notes/risks:** Providers remain fixture-backed only. No live API calls, cache
writes, live DB writes, notifications, paper trades, or execution were added.

## 2026-06-16 — Add fixture-backed exchange announcement providers · Codex
**Why:** The event radar needs direct exchange events in the dataset so proxy
fades can be tested against realistic negative/control cases. Phase 3 adds
exchange announcement parsing without enabling live network sources.
**Changes:**
- Added fixture-backed `BinanceAnnouncementProvider` and
  `BybitAnnouncementProvider`, plus shared announcement parsing helpers for
  spot/listing and perpetual/futures listing events.
- Added Binance and Bybit announcement fixtures covering TESTLIST spot listing
  and TESTPERP perp listing, plus alias entries for both assets.
- Event discovery can now combine manual raw-event fixtures, Binance
  announcements, Bybit announcements, and the cleaned CoinGecko universe fixture
  in one research-only report.
- Added optional config paths:
  `RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH` and
  `RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH`.
- Added offline tests for fixture parsing, malformed-provider fail-soft
  behavior, exchange-only scanner reports, and direct/no-trade safety for
  listing/perp events.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the Phase 3 exchange-provider status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 158/158.
`make event-discovery-report` prints TESTLIST and TESTPERP as direct
`NO_TRADE/DISCOVERED` candidates while TESTVELVET remains the only proxy trigger
fixture. `make verify` passes.
**Notes/risks:** Providers are fixture-backed only. No live exchange API calls,
DB writes, Telegram routing, paper trades, or execution were added.

## 2026-06-16 — Bridge event discovery to clean CoinGecko universe fixtures · Codex
**Why:** The event radar could resolve only manually aliased assets. The next
step was to let discovery use the same cleaned CoinGecko-style universe fixture
as the live scanner/backtest path, while staying offline and research-only.
**Changes:**
- Added `event_providers/coingecko_universe.py`, which loads local CoinGecko
  market rows, applies shared `universe.py` hygiene filters, and converts kept
  rows into `DiscoveredAsset` objects.
- Added optional `RSI_EVENT_DISCOVERY_UNIVERSE_PATH` and
  `RSI_EVENT_DISCOVERY_UNIVERSE_LIMIT` config, plus orchestration support to
  merge manual aliases with cleaned universe assets.
- Updated `make event-discovery-report` to exercise the checked-in
  `fixtures/coingecko_smoke/top_markets.json` universe fixture with no network
  calls, DB writes, alerts, paper trades, or execution.
- Added offline tests proving BTC/ETH/SOL become discovery assets, Tether is
  filtered out by shared hygiene, and the BTC ETF fixture can resolve to real
  `bitcoin` as a direct-beneficiary no-trade candidate.
- Updated `AGENTS.md`, `ROADMAP.md`, and `research/event_discovery_design.md`
  with the Phase 2 universe bridge status and guardrails.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 155/155.
`make event-discovery-report` prints the research-only radar with cleaned BTC
universe resolution and no writes/sends/trades. `make verify` passes.
**Notes/risks:** The universe bridge is fixture-only. It does not fetch
CoinGecko live data and does not add any live event provider.

## 2026-06-16 — Add fixture-only event discovery radar · Codex
**Why:** Event-fade scoring is structurally solid, but events were still manual
one-off inputs. Phase 1 needed a research-only radar that can normalize event
evidence, resolve assets conservatively, classify proxy vs direct-beneficiary
relationships, and feed structured candidates into `event_fade.py` without live
routing or storage.
**Changes:**
- Added discovery models and pipeline modules: `event_models.py`,
  `event_discovery.py`, `event_resolver.py`, `event_classification.py`, and
  `event_providers/` with a fixture-only manual JSON provider.
- Added `fixtures/event_discovery/raw_events.json` and
  `fixtures/event_discovery/asset_aliases.json` covering TESTVELVET/SpaceX proxy,
  TESTBTC ETF direct beneficiary, TESTTOKEN listing, TESTPUMP ambiguous pump,
  and a COLLIDE ticker collision that must not resolve confidently.
- Added research-only config and CLI/report wiring:
  `main.py --event-discovery-report` / `make event-discovery-report`. The report
  reads local fixtures only and does not write DB rows, send alerts, open paper
  trades, or execute anything.
- Added offline tests for provider loading, normalization/dedupe, alias
  resolution, ticker-collision rejection, proxy/direct/ambiguous classification,
  full pipeline output, event-fade safety, and scanner report plumbing.
- Added `research/event_discovery_design.md`, updated `AGENTS.md` architecture
  notes, and updated `ROADMAP.md` to reflect that the next work is expanding the
  reviewed validation sample.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 153/153.
`RSI_EVENT_DISCOVERY_EVENTS_PATH=fixtures/event_discovery/raw_events.json .venv/bin/python main.py --event-discovery-report`
prints the research-only event radar with TESTVELVET as proxy, TESTBTC/TESTTOKEN
as direct, TESTPUMP as ambiguous, and COLLIDE unresolved. `make verify` passes.
**Notes/risks:** This is still fixture-only. No network providers, JSONL cache
writes, live DB writes, Telegram routing, paper trades, or execution were added.

## 2026-06-16 — Self-score event-fade feature exports · Codex
**Why:** Review noted that `event_fade_feature_vector()` assumed callers had
already populated `component_scores`, which could silently export zeroed scores
from an otherwise valid candidate.
**Changes:**
- `crypto_rsi_scanner/event_fade.py` lets `event_fade_feature_vector()` accept
  optional `now` and automatically calculate fade scores when the candidate has
  not already been scored, without advancing the candidate state.
- `tests/test_indicators.py` adds regression coverage for unscored feature-vector
  export: scores and eligibility populate, while state remains `DISCOVERED`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 147/147.
`make verify` passes.
**Notes/risks:** Feature export can now mutate scoring metadata on an unscored
candidate, but still does not advance the event-fade state machine.

## 2026-06-16 — Hard-gate event-fade proxy eligibility · Codex
**Why:** External review caught that `is_event_fade_candidate()` had the right
proxy/direct-beneficiary rule, but the state machine treated proxy purity mostly
as a score component. That could let a high-scoring direct-beneficiary event
drift into a generic overextended-event short, which is not the event-fade thesis.
**Changes:**
- `crypto_rsi_scanner/event_fade.py` now enforces proxy eligibility before a
  candidate can advance beyond `DISCOVERED`; ineligible direct-beneficiary or
  non-proxy events emit `NO_TRADE` even if pump, crowding, RSI, and post-event
  failure evidence are strong.
- `event_fade_feature_vector()` now accepts an optional config and uses the same
  eligibility gate when reporting `signal_type`.
- `tests/test_indicators.py` adds regressions for direct-beneficiary and
  manually armed non-proxy events, plus config-sensitive feature-vector output.
- `AGENTS.md` and `DECISIONS.md` record the hard proxy gate as durable event-fade
  design, not just a test detail.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 147/147.
`RSI_EVENT_FADE_EVENTS_PATH=fixtures/event_fade/sample_events.json .venv/bin/python main.py --event-fade-report`
still prints `TESTVELVET SHORT_TRIGGERED`. `make verify` passes.
**Notes/risks:** Valid proxy-event fixtures still trigger; direct-beneficiary and
non-proxy events now stay diagnostic-only.

## 2026-06-16 — Make push-after-commit the collaboration rule · Codex
**Why:** The human wants GitHub to stay current so Claude, Codex, and external
ChatGPT review all see the latest committed project state.
**Changes:**
- `AGENTS.md` changes the core rule from "commit every change" to "commit and
  push every change", with standing approval to push `main` to `origin` after
  each commit.
- `CLAUDE.md` now repeats the three post-change requirements directly for
  Claude: DEVLOG, commit, push.
- `DECISIONS.md` records the durable decision and supersedes the older
  no-push-without-explicit-approval clause.
**Verify:** docs-only; `git diff --check` passes; `make verify` passes.
**Notes/risks:** Agents should still ask before force-pushing, changing remotes,
or pushing a different branch.

## 2026-06-16 — Add alert-only event-fade research sleeve · Codex
**Why:** The VELVET/SpaceX-style idea is not "short every overbought RSI pump";
it is a separate sell-the-news pattern around dated proxy catalysts, crowded
positioning, liquidity/supply fragility, and post-event failure. The system
needed a research-safe engine that can model that thesis without changing live
RSI alerts or implying execution.
**Changes:**
- `crypto_rsi_scanner/event_fade.py` adds a pure event-fade engine: dataclasses,
  component scores, state machine, post-event failure trigger, BTC risk-on block,
  risk sizing helper, feature-vector export, JSON fixture loaders, and an
  alert-only report formatter.
- `crypto_rsi_scanner/config.py`, `crypto_rsi_scanner/scanner.py`, `main.py`, and
  `Makefile` add inert-by-default event-fade tunables and
  `main.py --event-fade-report` / `make event-fade-report` for local fixture
  scoring only.
- `fixtures/event_fade/sample_events.json` adds a TESTVELVET proxy-event fixture
  that reaches `SHORT_TRIGGERED` only after the event and failure evidence.
- `tests/test_indicators.py` covers component scores, negative direct-beneficiary
  cases, no dated catalyst, post-event confirmation, BTC risk-on blocking, risk
  helpers, JSON loading, and passive feature-vector export.
- `research/event_fade.md`, `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md`
  document the event-fade thesis, constraints, next validation step, and durable
  rule that this remains alert-only until validated.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 145/145.
`RSI_EVENT_FADE_EVENTS_PATH=fixtures/event_fade/sample_events.json .venv/bin/python main.py --event-fade-report`
prints `TESTVELVET SHORT_TRIGGERED` with alert-only/no-order warning.
`git diff --check` passes. `make verify` passes.
**Notes/risks:** Phase 1 uses local/manual JSON inputs only. No live storage,
notification routing, paper trades, exchange execution, or existing RSI signal
behavior changed. Next step is a manually reviewed event-fade validation sample.

## 2026-06-15 — Add safe paper-trade refresh command · Codex
**Why:** Live paper-trade validation was blocked even after several positions
passed their 7-day hold, because paper exits only closed during the daily
non-dry-run scan. Triggering a full scan just to close trades can send alerts, so
the project needed a narrow non-alerting refresh path.
**Changes:**
- `crypto_rsi_scanner/scanner.py` adds `main.py --refresh-paper`, which fetches
  histories only for open paper-trade coins, calls the existing paper close logic
  with no new signals, and prints the refreshed scoreboard. It supports
  `--cohorts` and `--json` like `--score`.
- `main.py` and `AGENTS.md` document the new command.
- `tests/test_indicators.py` covers that the refresh command fetches open paper
  histories, passes an empty signal list, prints the report, and closes storage
  without running scan/alert plumbing.
- `ROADMAP.md` records that the first six paper trades closed but are still too
  small/outlier-dominated for strategy decisions.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 137/137.
`main.py --refresh-paper --cohorts` fetched 19/19 open histories and closed 6
trades. `make verify` passed after the change.
**Notes/risks:** The first closed paper sample is not decision-grade: 6 trades,
including one -95.7% SIREN outlier. Keep waiting for more closed paper trades
before promoting live priors or state cohorts.

## 2026-06-15 — Fix volume-PIT trigger comparison guardrails · Codex
**Why:** Review found that `--compare-triggers --pit-volume` silently used the
default trigger-comparison universe instead of the volume-PIT universe, and bad
research inputs like `--volume-window 0` could produce empty/noisy output instead
of a clear error.
**Changes:**
- `crypto_rsi_scanner/backtest.py` splits volume-PIT into fetch-once and
  walk-under-trigger helpers, adds `run_pit_volume_triggers()`, wires
  `--compare-triggers --pit-volume` through the real volume-ranked universe, and
  rejects invalid CLI values before any network/cache work.
- `build_volume_membership()` now rejects non-positive `top_n`/`window` values.
- The volume-PIT fetch path now closes its `requests.Session` and skips API
  throttling sleeps when a kline file is already cached.
- `tests/test_indicators.py` adds regression coverage for invalid inputs, the
  PIT-volume compare branch, and cache-hit sleep/session behavior.
- `AGENTS.md` documents that `--compare-triggers` supports `--pit-volume`.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 136/136.
`make verify` passes. Real smoke:
`.venv/bin/python -m crypto_rsi_scanner.backtest --compare-triggers --pit-volume --top-n 5 --days 1825 --volume-window 30`
runs on 368 usable volume-PIT histories and prints both trigger books.
**Notes/risks:** Research-tooling only; no live scanner scoring, routing, or
alert behavior changed.

## 2026-06-10 — Sync agent docs to the volume-PIT reality · Claude
**Why:** AGENTS.md still told agents PIT research was bear-only/365d and needed a
Pro key, and conviction was "unvalidated" — all superseded by the volume-PIT run.
Stale shared docs are how settled questions get relitigated.
**Changes:** AGENTS.md (flag list +`--pit-volume`; "PIT data depth: SOLVED";
conviction-validation status; research-path caveats now point to `--pit-volume`);
DECISIONS.md (new: "Volume-rank PIT is the standard full-cycle research universe").
**Verify:** docs-only; `make verify` green.

## 2026-06-10 — Volume-rank PIT universe: 5y survivorship-reduced backtest, no Pro key · Claude
**Why:** Every blocked research item (bull/chop validation, prior recalibration,
state-cohort confirmation) was gated on point-in-time history >365d, which the
mcap PIT path can't get on a demo CoinGecko key. Binance klines are free for ~5y
and carry quote (USDT) volume — so membership can be ranked by trailing dollar
volume instead of market cap.
**Changes:**
- `backtest.py`: `--pit-volume` mode — `binance_usdt_pool()` (exchangeInfo,
  hygiene-filtered; no leveraged-token suffix filter needed since those are all
  delisted, and JUP/SYRUP are real coins), `build_volume_membership()` (top-N by
  trailing `--volume-window`=30d mean quote volume, no lookahead),
  `run_pit_volume()` (walks on USD volume so volume_ratio matches live CoinGecko
  semantics). `fetch_klines` now returns `quote_volume` and caches raw rows under
  `backtest_cache/binance_klines/` (reuses the PIT cache flags; cache hit never
  touches the network).
- Tests: membership rolling-rank, pool hygiene filter, kline row parsing, cache
  roundtrip (132/132).
- `research/VOLUME_PIT_BACKTEST_2026-06-10.md` + prior export
  `research/registry_priors_volpit_2026-06-10.json`; ROADMAP: two "needs Pro
  key" items closed, follow-ups added.
**Verify:** `make verify` green (132/132 + smokes). Full run: 368 coins, 21,334
graded obs, balanced coverage (BULL 60.9k / CHOP 23.8k / BEAR 46.7k base-days).
**Results:** Gating map confirmed on survivorship-reduced full-cycle data —
mean_reversion CHOP **+10 (n=800)** third independent confirmation;
mean_reversion BULL −3; dip_buy/trend_continuation BULL positive but thin
(+6/+4); breakdown_risk no edge anywhere (context-only stays right). **Conviction
monotonic with edge for the first time** (low −3 / med +3 / high +9, n=307) —
first real validation of the registry edge-prior conviction. State-slice
replications: breakdown_risk crisis-vol −19; mean_reversion washout +14,
risk_on_broad −8.
**Notes/risks:** Residual survivorship (delisted pairs absent from exchangeInfo);
single venue; volume-rank ≠ live mcap universe. Prior export is reviewable only —
NOT loaded live (opt-in policy unchanged).

## 2026-06-09 — Fix review reliability gaps · Codex
**Why:** A fresh review found several boundary bugs: failed alert sends could
still advance cooldown/digest state, paper trades opened before matured same-coin
positions closed, live outcome reports could not directly validate gating, and
dry-run/universe-audit behavior had small honesty gaps.
**Changes:**
- `crypto_rsi_scanner/scanner.py` now skips CSV writes in dry-run mode, fetches
  extra recent histories for pending outcome/paper bookkeeping when coins leave
  today's clean universe, and only marks instant/digest notification state after
  a channel succeeds.
- `crypto_rsi_scanner/notifications.py` splits long Telegram messages into
  multiple line-aware chunks instead of truncating later cards.
- `crypto_rsi_scanner/storage.py` adds `signals.market_aligned`, backfills it
  additively, exposes pending signal/open paper coin IDs, and returns market/state
  context from `outcomes_joined()`.
- `crypto_rsi_scanner/outcomes.py` adds actionable/control, market-alignment, and
  state-cohort sections to `main.py --report`.
- `crypto_rsi_scanner/paper.py` closes matured trades before opening new
  crossings and treats missing falling-knife state as unknown, not low risk.
- `crypto_rsi_scanner/universe.py` stores all kept audit rows so suspicious-kept
  checks cover the full requested clean universe.
- `tests/test_indicators.py`, `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and
  `main.py` document and cover the reliability changes.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 128/128.
`main.py --report`, `make dry-run-fixture`, and `make score-cohorts` run
successfully. `make verify` passes tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** This changes live reliability/bookkeeping and reporting, but not
the core RSI setup taxonomy, conviction priors, or market-gating rules. The first
post-change `Storage` open migrates the ignored live DB with `market_aligned`.

## 2026-06-09 — Add cohort, cost, and walk-forward research tools · Codex
**Why:** The remaining improvement tracks needed tooling before any live signal
behavior changes: live cohort reads, cost/slippage-aware backtest output,
chronological stability checks, and a repeatable way to spot universe hygiene
leaks.
**Changes:**
- `crypto_rsi_scanner/paper.py`, `scanner.py`, `main.py`, and `Makefile` add
  `main.py --score --cohorts` / `make score-cohorts`, including state-bucket
  cohort stats from stored `state_json` once paper trades close.
- `crypto_rsi_scanner/backtest.py` adds `--costs`, `--fee-bps`,
  `--slippage-bps`, `--max-trades-per-day`, `--walk-forward`, and timestamped
  signal labels so research can inspect costs, capacity, drawdown, and fold
  stability before promoting calibration.
- `crypto_rsi_scanner/universe.py` adds suspicious-kept leak detection to the
  audit formatter for stable/wrapped/yield-like rows that survive filtering.
- `research/PIT_DATA_OPTIONS_2026-06-09.md` documents the current 365d PIT data
  limit, Pro-key/deeper-history workflow, alternate provider contract, and
  promotion rule.
- `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` record the new commands and the
  decision that cost/walk-forward outputs are research-only until a specific
  live rule is proposed.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 124/124.
`make score-cohorts`, `make backtest-costs`, and `make universe-audit` all run
successfully. `make verify` passes tests, alert render smoke, backtest fixture
smoke, and paper scoreboard.
**Notes/risks:** No live signal scoring, routing, or gating changed. Broader PIT
history still requires a Pro CoinGecko key or alternate historical market-cap
provider before registry priors should be promoted live.

## 2026-06-09 — Add universe audit refresh command · Codex
**Why:** After tightening hygiene filters, the project still had to wait for a
full scheduled scan to confirm the market-list filter. A lightweight refresh
path gives immediate feedback without running RSI analysis or sending alerts.
**Changes:**
- `crypto_rsi_scanner/scanner.py` adds `fetch_universe_audit()` plus
  `main.py --refresh-universe-audit`, which fetches current CoinGecko market
  rows, applies shared universe hygiene, persists the audit, and prints it.
- `Makefile` adds `make refresh-universe-audit`.
- `crypto_rsi_scanner/universe.py` now directly excludes symbols that start or
  end with `usd`, catching observed BFUSD/apxUSD leaks from the refreshed audit.
- `tests/test_indicators.py` covers the audit refresh helper with a fake
  CoinGecko client and the new USD-prefix/suffix examples.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` document the workflow and the
  refreshed audit result.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 122/122.
`make refresh-universe-audit` persisted a fresh audit: 200 fetched, 100 kept, 53
excluded (`stable_like=36`, `low_liquidity=17`). A kept-set regex scan found no
obvious USD/stable/yield leaks. `make verify` passes tests, alert render smoke,
backtest fixture smoke, and paper scoreboard after the documentation update.
**Notes/risks:** The command updates `universe_hygiene_latest.json` and the DB
meta audit, but does not run a full scan, send alerts, or alter signal state.

## 2026-06-09 — Tighten universe stable/pegged filters · Codex
**Why:** The next roadmap item was to review the latest live universe hygiene
audit for false positives/negatives. The 2026-06-09 03:10 MSK audit showed
stable/pegged products surviving into the kept top-100.
**Changes:**
- Reviewed `main.py --universe-audit`: 200 fetched, 100 kept, 41 excluded
  (`stable_like=19`, `low_liquidity=22`).
- `crypto_rsi_scanner/universe.py` now catches observed false negatives:
  USD1, Global Dollar/USDG, USDtb, United Stables, GHO, YLDS, USX, USYC,
  Tether Gold/XAUT, and PAX Gold/PAXG.
- `crypto_rsi_scanner/config.py` mirrors the safe symbol-only exclusions; the
  one-letter United Stables symbol is caught by name instead.
- `tests/test_indicators.py` covers the newly observed stable/pegged examples.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` record the audit result and the
  follow-up to re-check the next live audit.
**Verify:** Replayed the known kept false negatives through `exclusion_reason()`;
they now return `stable_like`. `.venv/bin/python tests/test_indicators.py`
passes 121/121. `make verify` passes tests, alert render smoke, backtest fixture
smoke, and paper scoreboard after the documentation update.
**Notes/risks:** Low-liquidity exclusions such as LEO were left unchanged. The
next scheduled scan should confirm these products no longer appear in the kept
universe.

## 2026-06-09 — Add offline backtest fixture smoke · Codex
**Why:** The final ready roadmap item was to make the backtest CLI smoke-testable
without relying on Binance/network availability.
**Changes:**
- `crypto_rsi_scanner/backtest.py` can load Binance-style daily kline CSVs via
  `--fixture-dir`, infer symbols from fixture filenames, and fail smoke runs with
  `--min-signals` when too few graded observations are produced.
- Added checked-in BTC/ETH/SOL 365d fixture snapshots under
  `fixtures/backtest_smoke/klines/` plus a fixture README.
- `Makefile` adds `make backtest-fixture` and includes it in `make verify`.
- `tests/test_indicators.py` covers fixture symbol inference and CSV parsing.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` document the completed fixture
  smoke and its verification role.
**Verify:** `make backtest-fixture` produces 3 usable coins and 33 graded
observations. `.venv/bin/python tests/test_indicators.py` passes 121/121.
`make verify` passes tests, alert render smoke, backtest fixture smoke, and paper
scoreboard after the documentation update.
**Notes/risks:** No live scanner logic changed. The fixture is a small smoke
dataset, not strategy evidence.

## 2026-06-09 — Review cached PIT registry priors · Codex
**Why:** The next roadmap research step was to export registry conviction priors
from point-in-time histories and decide whether the artifact is strong enough to
load live.
**Changes:**
- Ran `.venv/bin/python -m crypto_rsi_scanner.backtest --pit --top-n 80 --pool
  150 --days 365 --export-priors research/registry_priors_pit_2026-06-09.json`:
  150 cache hits, 128 usable histories, 1325 graded observations.
- Added `research/registry_priors_pit_2026-06-09.json` and
  `research/PIT_REGISTRY_PRIORS_REVIEW_2026-06-09.md` with the exported deltas
  and review-only decision.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` now record that the 365d PIT
  prior export is BEAR-only evidence and should not be loaded with
  `RSI_REGISTRY_PRIORS`.
**Verify:** PIT export completed successfully. `make verify` passes tests
120/120, alert render smoke, and paper scoreboard after the documentation
updates.
**Notes/risks:** No signal logic changed. The export moved
`mean_reversion.neutral` 42 -> 47 and `trend_continuation.neutral` 42 -> 40, but
that is not enough for live adoption because the market coverage was only BEAR.

## 2026-06-09 — Run cached PIT state-slice confirmation · Codex
**Why:** The next roadmap item was to use point-in-time membership to check
whether the current-top Binance state-slice candidates survive a less
survivorship-biased test.
**Changes:**
- Ran `.venv/bin/python -m crypto_rsi_scanner.backtest --pit --top-n 80 --pool
  150 --days 365 --state-slices`: cache started empty, populated 150 raw
  CoinGecko histories, used 128 histories, and produced 1325 graded observations.
- Added `research/PIT_STATE_SLICE_CONFIRMATION_2026-06-09.md` with the command,
  caveats, setup baseline, state-slice read, and no-live-change decision.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` record that this PIT result is
  bear-regime evidence only; bull/chop state candidates still need deeper PIT or
  live confirmation.
**Verify:** PIT run completed successfully and populated the local gitignored
cache. `make verify` passes tests 120/120, alert render smoke, and paper
scoreboard after the documentation update.
**Notes/risks:** No signal logic changed. The 365d demo CoinGecko PIT window
only had BTC `BEAR` market-regime coverage, so it supports monitoring
bear-regime `mean_reversion` and keeping `breakdown_risk` context-only, but does
not validate bull/chop rules.

## 2026-06-09 — Add PIT history cache for backtests · Codex
**Why:** PIT state-slice confirmation and registry calibration depend on
CoinGecko market-cap histories, which are rate-limit sensitive and expensive to
refetch. A local raw-history cache improves practical PIT research power even
before a deeper Pro/alternate data source is available.
**Changes:**
- `crypto_rsi_scanner/backtest.py` caches raw CoinGecko `market_chart` JSON for
  PIT histories, reads cached histories before network fetches, and adds
  `--pit-cache-dir`, `--no-pit-cache`, and `--refresh-pit-cache` flags.
- `crypto_rsi_scanner/config.py`, `.env.example`, and `.gitignore` add the
  configurable `RSI_BACKTEST_CACHE_DIR` (`backtest_cache` by default) and keep
  cached research data out of git.
- `tests/test_indicators.py` adds a PIT cache roundtrip test that loads a cached
  synthetic history without network.
- `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` document the cache behavior and
  the remaining data-source limit for >365d PIT history.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 120/120.
`.venv/bin/python -m crypto_rsi_scanner.backtest --help | rg
"pit-cache|refresh-pit-cache|no-pit-cache"` confirms the CLI flags. `make
verify` passes tests, alert render smoke, and paper scoreboard.
**Notes/risks:** This improves repeatability/resume behavior and larger-pool PIT
runs, but it does not bypass CoinGecko demo history limits. >365d PIT still needs
a Pro key or alternate historical market-cap source.

## 2026-06-09 — Run first larger state-slice review · Codex
**Why:** The next research step was to use `backtest --state-slices` on a larger
history and decide whether any shadow market-state buckets are ready for live
promotion.
**Changes:**
- Ran `.venv/bin/python -m crypto_rsi_scanner.backtest --top-n 80 --days 1460
  --state-slices`: 49 usable Binance histories, 7648 graded observations.
- Added `research/STATE_SLICE_BACKTEST_2026-06-09.md` with the command, caveats,
  setup baseline, market-regime check, candidate state cohorts, and no-promotion
  decision.
- `crypto_rsi_scanner/backtest.py` widens the state-slice table columns so long
  feature labels do not run into bucket names.
- `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md` record that these candidates
  need PIT/live confirmation before any live conviction/routing change.
**Verify:** Larger state-slice run completed successfully. Full local
verification was rerun after the docs/formatting update: `make verify` passes
tests 119/119, alert render smoke, and paper scoreboard.
**Notes/risks:** No live signal logic changed. Most plausible candidates are
documented, but the run is current-top survivorship-biased, single-venue, and
costless, so it is not enough to alter live alerts.

## 2026-06-09 — Add state-conditioned backtest slices · Codex
**Why:** Live scanner now stores shadow market-state context, but those labels
need a research path that can test conditional edge before any state bucket is
allowed to affect conviction or routing.
**Changes:**
- `crypto_rsi_scanner/state_features.py` exposes shared bucket/risk helpers for
  relative strength, liquidity, breadth state, and falling-knife risk so live and
  research use the same labels.
- `crypto_rsi_scanner/scanner.py` now consumes those shared helpers instead of
  private copies.
- `crypto_rsi_scanner/backtest.py` adds point-in-time state-frame construction,
  stores state labels on graded events, builds same-regime/same-state base-rate
  tables, and exposes `--state-slices` / `--state-min-samples` for research
  reports.
- `tests/test_indicators.py`, `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md`
  cover and document the new state-slice benchmark rule.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 119/119.
`.venv/bin/python -m crypto_rsi_scanner.backtest --help | rg
"state-slices|state-min-samples"` confirms the new CLI flags. `make verify`
passes tests, alert render smoke, and paper scoreboard.
**Notes/risks:** The state-slice report is still research-only. A bucket should
not be promoted into live conviction/routing unless it beats the same-regime,
same-state base rate with enough PIT/live observations.

## 2026-06-08 — Wire market-state context into live scanner · Codex
**Why:** The pure state feature layer needs live, reviewable observations before
any state-conditioned edge can be trusted. Scanner rows should therefore carry
volatility, breadth, relative-strength, liquidity, and falling-knife context
without changing current alert decisions.
**Changes:**
- `crypto_rsi_scanner/scanner.py` builds one shadow state context per scan,
  attaches per-coin `state_json`, `vol_state`, `breadth_state`, `rs_bucket`,
  `liquidity_bucket`, and `falling_knife_score` after conviction/tier are
  computed, and adds compact console tokens for meaningful state labels.
- `crypto_rsi_scanner/storage.py` additively migrates `signals` and
  `paper_trades` with nullable `state_json`; `crypto_rsi_scanner/paper.py`
  stores the entry-state snapshot for paper trades.
- `crypto_rsi_scanner/telegram.py` preserves compact state buckets in the latest
  bot snapshot.
- `tests/test_indicators.py`, `ROADMAP.md`, `DECISIONS.md`, and `AGENTS.md`
  document and test the shadow-only state boundary.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 117/117.
`make dry-run-fixture` runs offline and shows state tokens in the scan output.
`make smoke-alerts` passes. `make verify` passes tests, alert render smoke, and
paper scoreboard.
**Notes/risks:** State remains observational only. The next high-leverage work is
state-conditioned backtest/live cohort analysis before allowing any state bucket
to affect conviction or routing.

## 2026-06-08 — Add pure market-state feature layer · Codex
**Why:** The research plan keeps RSI as the event trigger but needs a separate,
auditable market-state layer before testing volatility, breadth, relative
strength, beta, liquidity, and falling-knife hypotheses.
**Changes:**
- New `crypto_rsi_scanner/state_features.py` adds pure helpers for realized
  volatility, trailing percentiles, volatility state labels, percentage returns,
  cross-sectional ranks, single/multi-factor beta, volume z-score, dollar
  volume, turnover, volume/price state, and breadth snapshots.
- `tests/test_indicators.py` adds standalone tests covering flat/changing
  volatility, trailing-only percentiles, volatility state rules, rank monotonicity,
  synthetic beta recovery, volume/liquidity classification, and breadth behavior
  with missing/short histories.
- `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` document the shadow-first state
  feature policy and next integration step.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 115/115.
`make verify` passes tests, alert render smoke, and paper scoreboard.
**Notes/risks:** This is intentionally not wired into scanner routing, conviction,
or registry priors. Next step is shadow-only scanner/backtest integration with
`state_json`.

## 2026-06-08 — Add maintenance agent, restore drill, fixtures, and audit outputs · Codex
**Why:** The scanner had backup/log commands, but the remaining system
improvements were still manual or not reviewable: scheduled maintenance,
restore proof, structured paper-score data, universe-hygiene audits, and offline
scanner fixtures.
**Changes:**
- `main.py --maintenance` now runs a safe DB backup, restores that backup into a
  temporary SQLite DB for verification, and rotates configured logs.
- `main.py --verify-restore` restore-checks the newest retained backup by
  default; `backups.py` exposes the reusable restore-drill primitive.
- `make install-maintenance-agent` installs/loads the daily launchd maintenance
  agent (`com.nasrenkaraf.rsimaintenance` by default) to run `--maintenance`.
- `main.py --score --json` emits structured paper-score data, and the text score
  report now includes market-alignment and conviction-bucket breakdowns.
- Live scans persist the latest universe hygiene audit to SQLite meta and
  `universe_hygiene_latest.json`; `main.py --universe-audit` prints it.
- `RSI_FIXTURE_DIR` enables CoinGecko fixture mode, with checked-in
  `fixtures/coingecko_smoke` powering `make dry-run-fixture`.
- `Makefile`, `.env.example`, `.gitignore`, `AGENTS.md`, `CLAUDE.md`,
  `ROADMAP.md`, and `DECISIONS.md` document the new commands and operating
  decisions.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 108/108.
`make verify` passes tests, alert render smoke, and paper scoreboard.
`main.py --verify-restore` passes against the latest backup. `make maintenance`
created and restore-checked `backups/rsi_scanner-20260608T185301Z.db`.
`make dry-run-fixture` runs the scanner offline from fixtures. The maintenance
LaunchAgent was installed at
`~/Library/LaunchAgents/com.nasrenkaraf.rsimaintenance.plist` and points at the
repo venv Python.
**Notes/risks:** `main.py --universe-audit` will show data after the next
non-dry live scan persists the first audit. The fixture smoke validates scanner
plumbing, not live CoinGecko availability.

## 2026-06-08 — Finish ops maintenance status, logs, and launchd helpers · Codex
**Why:** Safe backups existed, but operational health still did not show whether
the latest backup was fresh, logs could grow without a repo-owned rotation
command, and launchd service inspection required memorized shell commands.
**Changes:**
- `main.py --status` now reports newest backup freshness, retained backup count,
  and configured log sizes/rotation thresholds.
- New `crypto_rsi_scanner/ops.py` adds copy-truncate log rotation plus launchd
  scan/listener status parsing and listener restart helpers.
- `main.py`, `Makefile`, `config.py`, `.env.example`, `.gitignore`,
  `AGENTS.md`, `CLAUDE.md`, `ROADMAP.md`, and `DECISIONS.md` document and expose
  `--rotate-logs`, `--launchd-status`, and `--restart-listener`.
- `tests/test_indicators.py` covers backup freshness rendering, log rotation
  retention, and launchd output parsing.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 104/104.
`.venv/bin/python main.py --status` shows the live backup as `OK` and both logs
below rotation threshold. `.venv/bin/python main.py --launchd-status` reports
`com.nasrenkaraf.rsiscanner` loaded/not running with last exit 0 and
`com.nasrenkaraf.rsibot` running. `.venv/bin/python main.py --rotate-logs` keeps
the current small logs without rotating.
**Notes/risks:** This intentionally does not install or mutate launchd schedules;
use the new commands from an explicit scheduled job if/when the owner wants that.

## 2026-06-08 — Add safe SQLite DB backup command · Codex
**Why:** The scanner now has operational health reporting, but the live SQLite
DB still needed a safe recovery path. Because the DB runs in WAL mode and can be
open from the scan and listener, raw file copies are not reliable enough.
**Changes:**
- New `crypto_rsi_scanner/backups.py` uses SQLite's online backup API to create
  consistent snapshots, writes through a temp file, verifies the result with
  `PRAGMA integrity_check`, and prunes older backups by retention count.
- `main.py --backup-db` and `make backup-db` create a verified backup under
  `RSI_BACKUP_DIR` with `RSI_BACKUP_KEEP` retention.
- `config.py`, `.env.example`, `.gitignore`, `AGENTS.md`, `ROADMAP.md`, and
  `DECISIONS.md` document/configure the backup workflow and keep backup artifacts
  out of git.
- `tests/test_indicators.py` adds a temp-DB backup integrity and retention test.
**Verify:** `.venv/bin/python main.py --backup-db` created
`backups/rsi_scanner-20260608T182009Z.db`, size 0.20 MB, `integrity_check: ok`.
`make verify` passes: tests 101/101, alert render smoke, and paper scoreboard.
**Notes/risks:** Backup freshness is not yet shown in `--status`; ROADMAP keeps
that and log rotation as the next ops-hardening work.

## 2026-06-08 — Add scan status and bot health report · Codex
**Why:** The scanner had heartbeat alerts for crashes/degraded fetches, but no
single persisted view of the latest run state. If launchd missed a scan or a run
failed after fetching, the owner and bot had to infer health from logs.
**Changes:**
- `storage.py` now persists scan lifecycle status in SQLite meta: running,
  success, failure, start/finish times, last success/failure, fetch/analyze
  counts, signal counts, routing counts, outcome updates, and paper-trade updates.
- `scanner.py` records live scan start/success/failure status, preserves dry-run
  read-only behavior, returns notification routing counts, and adds
  `main.py --status`.
- New `status_report.py` renders one shared operational report for CLI and bot.
- `telegram.py` adds `/health` and `/status`, updates help text, and has the
  listener check stale successful scans with a one-alert-per-episode watchdog.
- `heartbeat.py`, `config.py`, and `.env.example` expose/tune stale-scan alerts
  via `RSI_STALE_SCAN_HOURS` and `RSI_STALE_CHECK_INTERVAL_SEC`.
- `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` document the status path and
  narrow remaining ops hardening to DB backups/log rotation.
- `tests/test_indicators.py` adds status lifecycle/report, bot escaping, stale
  watchdog, and WAL/busy-timeout coverage.
**Verify:** `.venv/bin/python main.py --status` prints current local DB health
(`health: OK`, last success fallback from the existing `scans` table). `make
verify` passes: tests 100/100, alert render smoke, and paper scoreboard.
**Notes/risks:** Existing live runs will show `scan state: unknown` until the next
non-dry scan writes the new status meta; last-success freshness still falls back
to the historical `scans` table.

## 2026-06-08 — SQLite WAL + busy_timeout for scan/listener concurrency · Claude
**Why:** The daily scan (launchd) and the always-on bot listener share one SQLite
file. Default rollback-journal mode makes readers and writers block each other, so
a scan write during a listener read (or vice versa) risks "database is locked".
**Changes:**
- `storage.py` `Storage.__init__`: open with `timeout=30`, `PRAGMA journal_mode=WAL`
  + `PRAGMA busy_timeout=30000`. WAL lets one reader + one writer proceed
  concurrently; busy_timeout backs the rarer writer/writer overlap.
- `.gitignore`: ignore the new `*.db-wal` / `*.db-shm` sidecars.
- `tests/test_indicators.py`: assert Storage opens in WAL with a busy_timeout.
**Verify:** `make verify` green (97/97 + smoke). Live DB confirmed `journal_mode=wal`;
listener restarted on new code (PID 54739); WAL sidecars present and gitignored.
**Notes:** WAL is persistent in the DB header; needs local disk (it's on the Mac's
local FS). No schema change.

## 2026-06-08 — Initialize local git + commit-per-prompt convention · Claude
**Why:** Two agents now edit the same files; git gives real diffs/blame/rollback
that a hand-maintained log can't. Human approved adopting it.
**Changes:**
- `git init` (branch `main`, no remote); initial commit of the full tree.
- `.gitignore`: also ignore `.claude/settings.local.json` (machine-local).
- New convention in `AGENTS.md`/`CLAUDE.md`: end every change-making prompt with one
  commit, `make verify` green, no secrets/artifacts, on `main`, no push without approval.
- `DECISIONS.md`: superseded the two "no git" decisions; added the adoption decision.
  `ROADMAP.md`: dropped the "evaluate git" item.
**Verify:** `make verify` green; `git status` clean post-commit; confirmed `.env`,
`*.db`, logs, `.venv`, `.claude/settings.local.json` are untracked.
**Notes:** local-only; adding a remote/push needs explicit human approval (DECISIONS).

## 2026-06-07 — Fix NaN crash in alert render (DataFrame self-tune) · Claude
**Why:** The registry refactor's `_apply_live_edge_adjustments` creates
`track_record`/`conviction_base` columns via `df.at`, leaving NaN on rows without
a value. Once 7d live outcomes accrue, `_tg_card` joins a NaN float →
`TypeError: expected str, got float` → every alert send would crash silently.
**Changes:**
- `formatting._tg_card`: guard `track_record` + `conviction_base` with `_present`
  (rejects None *and* NaN).
- `scanner._apply_live_edge_adjustments`: pre-create both columns as object/None so
  unset rows stay None, not NaN (also keeps the bot snapshot JSON clean).
- `tests/test_indicators.py`: render-guard + end-to-end (apply→build_message→render)
  regression tests.
**Verify:** reproduced the crash with forced 7d stats, confirmed fixed; suite green.
**Notes:** Codex's later `alert_smoke.py` (DOGE NaN fixture) independently backstops
this at the render layer.

## 2026-06-07 — Add alert render smoke test · Codex
**Why:** Alert rendering has become a critical path with rich Telegram HTML,
plain-text fallbacks, macro headers, digest caps, track-record annotations, and
NaN-prone DataFrame enrichment. A signal-math test can pass while a notification
render still crashes or produces invalid Telegram markup.
**Changes:**
- New `crypto_rsi_scanner/alert_smoke.py` builds representative instant/digest
  payloads and validates Telegram HTML tags, message lengths, digest group caps,
  NaN/unsafe substring leaks, and plain fallback truncation behavior without
  sending network notifications.
- `Makefile` adds `make smoke-alerts` and includes it in `make verify`.
- `formatting.py` now escapes quotes in chart-link `href` attributes.
- `tests/test_indicators.py` adds the smoke suite test and a direct regression
  test for quoted symbols in chart links.
- `AGENTS.md` and `DECISIONS.md` document alert-render smoke as part of standard
  verification.
**Verify:** `.venv/bin/python -m crypto_rsi_scanner.alert_smoke` passes. `.venv/bin/python tests/test_indicators.py`
passes 96/96. `make verify` passes: tests 96/96, alert render smoke, and paper
scoreboard.
**Notes/risks:** The smoke is fixture-based and no-send/no-network; it catches
render regressions but does not validate Telegram API delivery.

## 2026-06-07 — Add backtest-to-registry calibration path · Codex
**Why:** Registry priors were still hand-coded from qualitative backtest findings.
The system needed a repeatable way to turn backtest evidence into reviewable
runtime priors without silently changing live alerts after a noisy smoke run.
**Changes:**
- `crypto_rsi_scanner/backtest.py` adds pure calibration/export helpers plus
  `--export-priors PATH` and `--prior-min-samples`. The export JSON includes run
  metadata, setup priors, default priors, and setup x market-regime evidence.
- Calibration is conservative: it starts from current registry priors, moves only
  sample-backed setup x market cells, clamps swings, and keeps `breakdown_risk`
  context-only even if a short sample shows apparent edge.
- `crypto_rsi_scanner/signal_registry.py` can load explicit JSON overrides from
  `RSI_REGISTRY_PRIORS`, validates schema/values, resolves relative paths against
  the project root, and falls back to checked-in defaults on missing/invalid
  calibration.
- `tests/test_indicators.py` adds deterministic tests for explicit override
  loading and evidence-driven prior calibration.
- `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and `.env.example` document the
  calibration workflow and opt-in policy.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 94/94. `make verify`
passes: tests 94/94 and paper scoreboard runs. Smoke export passes:
`.venv/bin/python -m crypto_rsi_scanner.backtest --top-n 5 --days 365 --export-priors /tmp/rsi_registry_priors_smoke_topn.json`
with 5 usable coins and 63 graded observations; exported JSON reloads through
`signal_registry.load_prior_overrides`.
**Notes/risks:** The smoke artifact is intentionally not enabled live; it is only
a CLI/schema check. Use a stronger PIT or longer-history run before setting
`RSI_REGISTRY_PRIORS` in `.env`.

## 2026-06-07 — Add shared universe hygiene filters · Codex
**Why:** CoinGecko top market-cap lists include stablecoins, wrapped/staked
receipts, stale/suspicious listings, and low-liquidity artifacts that pollute
alerts, outcomes, paper trades, and backtests.
**Changes:**
- New `crypto_rsi_scanner/universe.py` with pure filters for stable-like assets,
  wrapped/staked/synthetic derivatives, invalid market data, low volume/market
  cap, and suspicious 24h moves.
- `scanner.py` now overfetches CoinGecko candidates, applies shared hygiene, logs
  exclusion reason counts, and scans the first clean requested top-N.
- `backtest.py` uses the same hygiene for CoinGecko top-N/PIT candidate
  selection.
- `config.py` adds universe hygiene tunables and removes `stx` from hard symbol
  excludes so Stacks is not accidentally filtered.
- `.env.example`, `AGENTS.md`, `ROADMAP.md`, and `DECISIONS.md` document the new
  shared universe policy.
- Tests added for stable/wrapped/low-liquidity/suspicious exclusions, overfetch
  capping, and the `STX` false-positive case.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 92/92. `make verify`
passes. Backtest smoke check passes:
`.venv/bin/python -m crypto_rsi_scanner.backtest --top-n 5 --days 365`.
Live dry-run passes: `.venv/bin/python main.py --dry-run --top-n 5` fetched 55
candidates, excluded 2 stable-like entries, and scanned 5 clean coins.
**Notes/risks:** Filters are conservative and log reason counts; review live
logs for false positives/negatives before tightening further.

## 2026-06-07 — Backfill NaN-safe live-edge rendering fix · Codex
**Why:** Claude fixed a latent alert-rendering regression after the DataFrame
self-tune refactor, but stopped before logging it. Without the fix, rows without
track-record history could carry `NaN` into Telegram card rendering once live
7-day outcomes accrue.
**Changes:**
- `scanner.py` pre-creates `track_record` and `conviction_base` as object/`None`
  columns before live-edge enrichment, avoiding NaN-filled columns for unmatched
  rows.
- `formatting.py` guards `track_record` and `conviction_base` with `_present()`
  before rendering, so `None`/NaN values do not crash or leak into alerts.
- `tests/test_indicators.py` adds regression tests for direct Telegram card
  rendering and the apply/build/render path.
**Verify:** `make verify` passes: standalone tests 89/89 and paper scoreboard runs.
**Notes/risks:** This is a DEVLOG backfill of Claude's fix, not a new behavioral
change by Codex.

## 2026-06-07 — Add signal registry and edge-prior conviction · Codex
**Why:** Setup intent, market eligibility, and conviction priors were spread
across modules, and conviction still leaned too heavily on fixed severity
weights despite backtest findings.
**Changes:**
- New `crypto_rsi_scanner/signal_registry.py` as the canonical source for setup
  definitions, expected directions, market alignment, and edge-prior conviction
  baselines.
- `indicators.py` now delegates setup/market helpers to the registry and blends
  registry edge priors with severity/confluence in `conviction_score`.
- `scanner.py` uses registry-based conviction directly and applies mature live
  outcome self-tuning before printing, saving CSV/DB rows, snapshots, and alerts.
- `backtest.py`, `outcomes.py`, `paper.py`, `formatting.py`, and `storage.py`
  now consume registry definitions instead of duplicated/private setup maps.
- Tests added for registry coverage, backtest market aliases, and edge-prior
  conviction ordering.
- Updated `AGENTS.md`, `ROADMAP.md`, `DECISIONS.md`, and `config.py` comments to
  reflect the new source of truth.
**Verify:** `.venv/bin/python tests/test_indicators.py` passes 87/87. `make verify`
passes: tests 87/87 and paper scoreboard runs. Backtest smoke check passes:
`.venv/bin/python -m crypto_rsi_scanner.backtest --symbols BTC,ETH,SOL --days 365`.
**Notes/risks:** Registry priors encode the current qualitative backtest findings;
`ROADMAP.md` keeps numeric recalibration with stronger PIT/live evidence as a
future task.

## 2026-06-07 — Add roadmap, decisions log, and verify command · Codex
**Why:** The collaboration protocol had a history file, but no single place for
pending work, durable accepted/rejected decisions, or a standard verification
command.
**Changes:**
- New `ROADMAP.md` for live pending work, statuses, and priorities.
- New `DECISIONS.md` for durable technical decisions and revisit conditions.
- New `Makefile` with `make verify`, `make test`, `make score`, `make report`,
  and `make dry-run`.
- Updated `AGENTS.md` and `CLAUDE.md` to point both agents at the new files and
  standard verification path.
**Verify:** `make verify` passes: standalone tests 85/85, paper scoreboard runs.
**Notes/risks:** Did not initialize local git; `DECISIONS.md` records that agents
should wait for explicit human approval before changing the repo workflow.

## 2026-06-07 — Add shared AI-collaboration system (AGENTS.md + DEVLOG.md) · Claude
**Why:** Owner is now co-developing with Codex; we need a shared protocol + change
history (no git repo to lean on).
**Changes:**
- New `AGENTS.md` (shared brain: run/test/deploy, architecture, conventions,
  strategy findings, the "log every change" rule).
- New `DEVLOG.md` (this file) with template + backfilled session history.
- New `CLAUDE.md` (thin pointer so Claude Code follows AGENTS.md/DEVLOG).
**Verify:** docs only; `tests/test_indicators.py` still 85/85.
**Notes:** Codex reads `AGENTS.md` natively; Claude reads `CLAUDE.md` → both land here.

## 2026-06-07 — Confirmation entry trigger: A/B'd, REJECTED (backtest only) · Claude
**Why:** Test whether entering when RSI turns back *out* of the OB/OS zone beats
piercing *into* it (catching the knife).
**Changes:** `backtest.py` — `trigger` param on `walk_coin` (cross_into|confirm via
zone-state), `_fetch_all`/`_walk_all` refactor, `run_triggers`, `--trigger` /
`--compare-triggers`, `format_trigger_comparison`. Test added.
**Verify:** 5y/38-coin A/B: actionable book @7d ~identical (52%/+0.0% vs 51%/−0.0%);
confirm slightly hurts dip_buy & mean_reversion. **Live scanner UNCHANGED.**
**Notes/risks:** Negative result — don't re-add confirmation without new evidence.
Tooling kept for future variant A/Bs. Aggregate live edge is thin & regime-specific.

## 2026-06-07 — Paper-trade scoreboard · Claude
**Why:** Honest live proof of whether the (gated) signals make money.
**Changes:** new `paper.py`; `storage.py` `paper_trades` table + accessors;
`scanner.run` opens/closes trades each scan; `--score` CLI + `/score` bot command;
`config.PAPER_*`. Opens a virtual long/short per new crossing, closes after 7d at
that day's close (reuses fetched prices). Report: **actionable vs control book**,
by setup, by market regime.
**Verify:** 84→ tests pass; live `--score` works; synthetic demo shows the split.
**Notes:** Empty until ~7d of live scans mature trades. 1 unit/trade, horizon exit,
overlap-ignored equity (stated in the report).

## 2026-06-07 — Live market-regime gating · Claude
**Why:** Backtest showed edge is regime-conditional; gate each setup to its
favorable BTC regime.
**Changes:** `indicators.market_alignment` / `market_conviction_adjustment` /
`setup_has_edge` + edge map; `scanner` computes `trend_regime(BTC)` per scan, folds
alignment into conviction (±`MARKET_ALIGN_SWING`=12), `classify_tier` demotes
adverse non-extreme to DIGEST; `formatting` adds 🧭 market line + mutes
breakdown_risk direction; `storage` persists `market_regime`; `RSI_MARKET_GATING`.
**Verify:** 80 tests; dry-run showed BTC=DOWNTREND → adverse setups held to digest,
0 INSTANT.
**Notes:** edge map: mean_reversion→CHOP, dip_buy/trend_continuation→BULL,
breakdown_risk→never.

## 2026-06-07 — Backtester: deeper history + market-regime split · Claude
**Why:** 2y window was one regime (missed the 2022 bear); must separate bull/bear.
**Changes:** `backtest.py` — paginated Binance fetch (5y), `market_regime_series`
(BTC bull/bear/chop), `summarize_market`/`format_market`, default `--days 1460`.
**Verify:** 5y/39-coin run; balanced coverage (BULL 22k / BEAR 15.7k / CHOP 8.7k).
**Notes:** KEY FINDING — blended averages hid regime-conditional edge (see AGENTS.md).

## 2026-06-07 — Backtester: point-in-time universe (survivorship fix) · Claude
**Why:** Using today's top-N over history is survivorship-biased.
**Changes:** `backtest.py` — `--pit`/`--pool`, CoinGecko market-cap history,
`build_pit_membership` (per-date top-N), `walk_coin` `member` mask gates
signals+base.
**Verify:** PIT run (114 coins, 365d). Confirmed breakdown_risk's "bounce" was
survivorship-inflated (~0 under PIT).
**Notes:** demo CoinGecko key caps history at 365d → small samples; pro key extends.

## 2026-06-07 — Backtester: conditional vol/momentum slice · Claude
**Why:** Does oversold-in-downtrend only continue down in high-vol crashes?
**Changes:** `backtest.py` — per-day vol/momentum features, `conditional_table`
(terciles, base conditioned on same bucket), `--slice`.
**Verify:** breakdown_risk bounces MORE in high vol — crash-continuation hypothesis
refuted.

## 2026-06-07 — Backtester: initial build · Claude
**Why:** Validate signal edge over years, not the ~1 week of live data.
**Changes:** new `backtest.py` — replays the pure functions over Binance 1d klines,
grades each setup vs its regime base rate (anti-tautology benchmark). Use
`data-api.binance.vision` (api.binance.com 451s from MSK).
**Verify:** first run overturned the live read — breakdown_risk "98%" was the
tautology trap; real edge in dip_buy/mean_reversion.

## 2026-06-07 — Split signal intent (setup_type) + re-grade history · Claude
**Why:** `favorable` was hardcoded mean-reversion, mislabeling continuation setups.
**Changes:** `indicators.setup_for` + `_SETUP_MAP`; `scanner` stamps
setup_type/expected_dir; `outcomes.favorable(expected_dir,…)` + setup-keyed
reports; `storage` columns + one-time lossless re-grade (meta `setup_regrade_v1`);
`formatting`/`telegram` show the setup hypothesis.
**Verify:** 61→65 tests; re-graded 197 historical outcomes losslessly.

## 2026-06-07 — Ops fixes: bot.log spam, token leak, dead return · Claude
**Why:** Listener spammed ~18k identical DNS errors (with the bot token in the URL);
`telegram.listen()` had an unreachable `return added` (NameError on Ctrl-C).
**Changes:** `telegram.py` — `_Unreachable` for transient net errors, once-per-outage
log + exponential backoff, removed dead `return`; `config.redact_token`;
`notifications.py` scrubs token in logs.
**Verify:** 61 tests; listener restarted clean; truncated the 6.8MB bot.log.
