PYTHON ?= .venv/bin/python
EVENT_FIXTURE_NOW ?= 2026-06-15T16:00:00Z
EVENT_RESEARCH_NOW ?=
EVENT_FIXTURE_NOW_ENV = RSI_EVENT_RESEARCH_NOW=$(EVENT_FIXTURE_NOW)
EVENT_RESEARCH_NOW_ENV = $(if $(strip $(EVENT_RESEARCH_NOW)),RSI_EVENT_RESEARCH_NOW=$(EVENT_RESEARCH_NOW),)
EVENT_FADE_SAMPLE_OUT ?= /tmp/event_fade_validation_sample.jsonl
EVENT_FADE_SAMPLE_IN ?= $(EVENT_FADE_SAMPLE_OUT)
EVENT_FADE_SAMPLE_FRESH ?= $(EVENT_FADE_SAMPLE_OUT)
EVENT_FADE_SAMPLE_REVIEWED ?= $(EVENT_FADE_SAMPLE_IN)
EVENT_FADE_SAMPLE_MERGED ?= /tmp/event_fade_validation_merged.jsonl
EVENT_FADE_SAMPLE_OUTCOMES ?= /tmp/event_fade_validation_with_outcomes.jsonl
EVENT_FADE_REVIEW_PACKET_OUT ?= /tmp/event_fade_review_packet.md
EVENT_FADE_REVIEW_TEMPLATE_OUT ?= /tmp/event_fade_review_template.csv
EVENT_FADE_REVIEW_TEMPLATE ?= $(EVENT_FADE_REVIEW_TEMPLATE_OUT)
EVENT_FADE_SAMPLE_REVIEW_APPLIED ?= /tmp/event_fade_validation_review_applied.jsonl
EVENT_FADE_REVIEW_BUNDLE_DIR ?= /tmp/event_fade_review_bundle
EVENT_FADE_REVIEW_BUNDLE_SAMPLE ?= $(EVENT_FADE_REVIEW_BUNDLE_DIR)/validation_sample.jsonl
EVENT_FADE_REVIEW_BUNDLE_TEMPLATE ?= $(EVENT_FADE_REVIEW_BUNDLE_DIR)/review_template_balanced.csv
EVENT_FADE_REVIEW_BUNDLE_APPLIED ?= $(EVENT_FADE_REVIEW_BUNDLE_DIR)/validation_sample_reviewed.jsonl
EVENT_FADE_REVIEW_BUNDLE_OUTCOME_PRICES ?= $(EVENT_FADE_REVIEW_BUNDLE_DIR)/outcome_prices.json
EVENT_FADE_REVIEW_BUNDLE_OUTCOMES ?= $(EVENT_FADE_REVIEW_BUNDLE_DIR)/validation_sample_reviewed_with_outcomes.jsonl
EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR ?= /tmp/event_fade_cache_review_bundle
EVENT_FADE_REVIEW_BUNDLE_PRICES ?=
EVENT_FADE_REVIEW_BUNDLE_REVIEWED ?=
EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES ?=
EVENT_FADE_QUEUE_LIMIT ?= 20
EVENT_DISCOVERY_CACHE_DIR ?= event_fade_cache
EVENT_FADE_OUTCOME_PRICES ?= fixtures/event_discovery/outcome_prices.json
EVENT_FADE_OUTCOME_PRICES_OUT ?= /tmp/event_fade_outcome_prices.json
EVENT_FADE_PRICE_DAYS ?= 30
EVENT_FADE_PRICE_FIXTURE_DIR ?=
EVENT_FADE_PRICE_INTERVAL ?= 1d
EVENT_FADE_PRICE_FIXTURE_ARG = $(if $(strip $(EVENT_FADE_PRICE_FIXTURE_DIR)),--event-fade-price-fixture-dir $(EVENT_FADE_PRICE_FIXTURE_DIR),)
EVENT_DISCOVERY_RSS_URLS_PATH ?= fixtures/event_discovery/public_rss_feeds.txt
EVENT_DISCOVERY_RSS_UNIVERSE_LIVE ?= 1
EVENT_DISCOVERY_RSS_UNIVERSE_FETCH_LIMIT ?= 250
EVENT_DISCOVERY_RSS_LOOKBACK_HOURS ?= 720
EVENT_DISCOVERY_GDELT_QUERY ?= ("pre-ipo" OR "pre ipo" OR "synthetic exposure" OR "tokenized stock" OR "prediction market" OR "fan token")
EVENT_DISCOVERY_GDELT_MAX_RECORDS ?= 50
EVENT_DISCOVERY_GDELT_UNIVERSE_LIVE ?= 1
EVENT_DISCOVERY_GDELT_UNIVERSE_FETCH_LIMIT ?= 250
EVENT_DISCOVERY_GDELT_LOOKBACK_HOURS ?= 720
EVENT_DISCOVERY_POLYMARKET_LIMIT ?= 100
EVENT_DISCOVERY_POLYMARKET_UNIVERSE_LIVE ?= 1
EVENT_DISCOVERY_POLYMARKET_UNIVERSE_FETCH_LIMIT ?= 250
EVENT_ALERT_LLM_MODE ?= advisory
EVENT_ALERT_LLM_PROVIDER ?= fixture
EVENT_ALPHA_UNIVERSE_PATH ?= fixtures/coingecko_smoke/top_markets.json
EVENT_ALPHA_ANOMALY_MIN_RETURN_24H ?= 0.03
EVENT_ALPHA_ANOMALY_MIN_VOLUME_MCAP ?= 0.05
EVENT_CATALYST_SEARCH_FIXTURE_PATH ?=
EVENT_ALPHA_ARTIFACT_BASE_DIR ?= $(EVENT_DISCOVERY_CACHE_DIR)
EVENT_ALPHA_ARTIFACT_NAMESPACE ?= $(PROFILE)
EVENT_ALPHA_PROFILE_DIR ?= $(EVENT_ALPHA_ARTIFACT_BASE_DIR)/$(EVENT_ALPHA_ARTIFACT_NAMESPACE)
EVENT_ALPHA_FIXTURE_DIR ?= $(EVENT_ALPHA_ARTIFACT_BASE_DIR)/fixture
EVENT_WATCHLIST_STATE_PATH ?= $(EVENT_ALPHA_PROFILE_DIR)/event_watchlist_state.jsonl
EVENT_ALPHA_ALERT_STORE_PATH ?= $(EVENT_ALPHA_PROFILE_DIR)/event_alpha_alerts.jsonl
EVENT_ALPHA_NOTIFICATION_RUNS_PATH ?= $(EVENT_ALPHA_PROFILE_DIR)/event_alpha_notification_runs.jsonl
EVENT_ALPHA_RUN_LEDGER_PATH ?= $(EVENT_ALPHA_PROFILE_DIR)/event_alpha_runs.jsonl
EVENT_IMPACT_HYPOTHESIS_STORE_PATH ?= $(EVENT_ALPHA_PROFILE_DIR)/event_impact_hypotheses.jsonl
EVENT_ALPHA_MISSED_PATH ?= $(EVENT_ALPHA_PROFILE_DIR)/event_alpha_missed.jsonl
EVENT_ALPHA_PRIORS_OUT ?= $(EVENT_ALPHA_PROFILE_DIR)/event_alpha_priors.json
EVENT_PROVIDER_HEALTH_PATH ?= $(EVENT_ALPHA_PROFILE_DIR)/event_provider_health.json
EVENT_ALPHA_DAILY_BRIEF_PATH ?= $(EVENT_ALPHA_PROFILE_DIR)/event_alpha_daily_brief.md
EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR ?= $(EVENT_ALPHA_PROFILE_DIR)/proposed_eval_cases
EVENT_RESEARCH_CARDS_DIR ?= $(EVENT_ALPHA_PROFILE_DIR)/research_cards
EVENT_ALPHA_ALERT_OUTCOMES ?= $(EVENT_ALPHA_PROFILE_DIR)/event_alpha_alerts_with_outcomes.jsonl
EVENT_ALPHA_ALERT_PRICES ?= fixtures/event_discovery/outcome_prices.json
PROFILE ?= no_key_live
ALERT_KEY ?=
FEEDBACK_TARGET ?=
FEEDBACK_NOTES ?=
CONFIRM ?= 0
STRICT ?= 0
INCLUDE_LEGACY ?= 0
LATEST ?= 0
ALL_HISTORY ?= 0
RUN_ID ?=
SINCE ?=
IGNORE_BACKOFF ?= 0
PROVIDER_KEY ?=
PROVIDER_SERVICE ?=
PROVIDER_ROLE ?=
PROVIDER_ALL ?= 0
EVENT_ALPHA_BURN_IN_PACK ?= event_alpha_burn_in_pack.zip
EVENT_ALPHA_NOTIFICATION_PACK ?= event_alpha_notification_pack.zip
EVENT_ALPHA_LAUNCHD_OUT ?= research/generated_$(PROFILE).plist
EVENT_ALPHA_INCLUDE_LEGACY_ARG = $(if $(filter 1 true yes,$(INCLUDE_LEGACY)),--event-alpha-include-legacy-artifacts,)
EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT_ARG = $(if $(filter 1 true yes,$(STRICT)),--event-alpha-artifact-doctor-strict,)
EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT_LEGACY_ARG = $(if $(filter 1 true yes,$(STRICT_LEGACY)),--event-alpha-artifact-doctor-strict-legacy,)
EVENT_ALPHA_IGNORE_BACKOFF_ARG = $(if $(filter 1 true yes,$(IGNORE_BACKOFF)),--ignore-provider-backoff,)
EVENT_ALPHA_PROVIDER_SELECTOR_ARGS = $(if $(strip $(PROVIDER_KEY)),--provider-key $(PROVIDER_KEY),) $(if $(strip $(PROVIDER_SERVICE)),--service $(PROVIDER_SERVICE),) $(if $(strip $(PROVIDER_ROLE)),--role $(PROVIDER_ROLE),) $(if $(filter 1 true yes,$(PROVIDER_ALL)),--all,)
EVENT_ALPHA_NOTIFY_EVERY_RUN_PROFILES = notify_no_key notify_llm notify_llm_deep notify_llm_quality
EVENT_ALPHA_NOTIFY_DEDUPE_BY_CONTENT = $(if $(filter $(EVENT_ALPHA_NOTIFY_EVERY_RUN_PROFILES),$(PROFILE)),0,1)
EVENT_ALPHA_NOTIFY_DEDUPE_WINDOW_HOURS = $(if $(filter $(EVENT_ALPHA_NOTIFY_EVERY_RUN_PROFILES),$(PROFILE)),0,24)
EVENT_ALPHA_TEST_ARTIFACT_PROFILES = quality_validation catalyst_frame_validation catalyst_frame_e2e notify_llm_quality_frame
EVENT_ALPHA_INCLUDE_TEST_ARG = $(if $(filter $(EVENT_ALPHA_TEST_ARTIFACT_PROFILES),$(PROFILE)),--event-alpha-include-test-artifacts,)

.PHONY: help check-python bootstrap export-src verify test smoke-alerts backtest-fixture backtest-costs score score-json score-cohorts report event-fade-report event-discovery-report event-discovery-status event-discovery-runs event-discovery-refresh event-discovery-refresh-configured event-discovery-refresh-public-rss event-discovery-refresh-gdelt event-discovery-refresh-polymarket event-discovery-binance-listen event-llm-eval event-llm-extract-eval event-alpha-eval event-alpha-catalyst-frame-validation-cycle event-alpha-catalyst-frame-e2e-cycle event-alpha-notify-llm-quality-frame-smoke event-alpha-frame-quality-loop event-alpha-signal-quality-eval event-alpha-quality-review event-alpha-quality-coverage-report event-alpha-quality-validation-cycle event-alpha-notify-llm-quality-validation-cycle event-alpha-notify-llm-quality-fresh-cycle event-alpha-quality-live-smoke event-alpha-policy-simulate event-alpha-export-signal-quality-cases event-alpha-quality-loop event-alpha-quality-loop-llm event-opportunity-audit event-alpha-no-key-report event-catalyst-search-fixture-report event-alpha-cycle event-alpha-cycle-llm event-alpha-cycle-search event-alpha-cycle-search-llm event-alpha-cycle-send event-alpha-cycle-profile event-alpha-cycle-profile-send event-alpha-notify-cycle event-alpha-notify-no-key event-alpha-notify-llm event-alpha-notify-preview event-alpha-notify-go-no-go event-alpha-environment-doctor event-alpha-pause-notifications event-alpha-resume-notifications event-alpha-scheduler-status event-alpha-generate-launchd event-alpha-notification-slo-report event-alpha-export-notification-pack event-alpha-notification-checklist event-alpha-notification-runs-report event-alpha-notification-inbox event-alpha-notification-deliveries-report event-alpha-notification-retry-failed event-alpha-notify-no-key-scheduled event-alpha-notify-llm-scheduled event-alpha-notify-llm-deep-scheduled event-alpha-notify-llm-quality-scheduled event-alpha-provider-health-report event-alpha-provider-health-reset event-alpha-day1-start event-alpha-day1-start-llm event-alpha-notify-fixture-smoke event-alpha-notify-start-no-key event-alpha-notify-start-llm event-alpha-send-test event-alpha-telegram-recipient-check event-alpha-runs-report event-alpha-status event-alpha-preflight event-alpha-daily-report event-alpha-daily-llm-report event-alpha-daily-send event-alpha-health event-alpha-health-guard event-alpha-artifact-doctor event-alpha-v1-readiness event-alpha-tuning-worksheet event-alpha-export-burn-in-pack event-alpha-launchd-template event-alpha-open-items event-alpha-daily-brief event-alpha-prune-artifacts event-alpha-replay event-alpha-priors-shadow-report event-alpha-burn-in-no-key event-alpha-burn-in-llm event-alpha-weekly-review event-alpha-burn-in-scorecard event-alpha-burn-in-checklist event-feedback-useful event-feedback-junk event-feedback-watch event-alpha-alerts-report event-alpha-fill-outcomes event-watchlist-refresh event-watchlist-report event-watchlist-monitor event-alpha-router-report event-alpha-missed-report event-alpha-near-miss-report event-alpha-calibration-report event-source-reliability-report event-alpha-calibration-export-priors event-alpha-export-eval-cases event-alpha-explain-last-run event-research-cards event-research-cards-write event-feedback-report event-incidents-report event-alert-no-key-report event-alert-no-key-llm-report event-alert-no-key-send event-fade-auto-report event-fade-export-sample event-fade-export-cache-sample event-fade-review-sample event-fade-labeling-queue event-fade-review-packet event-fade-export-review-template event-fade-apply-review-template event-fade-check-review-template event-fade-check-review-bundle event-fade-apply-review-bundle event-fade-review-applied-bundle event-fade-fill-review-bundle-outcomes event-fade-review-bundle event-fade-cache-review-bundle event-fade-review-cycle event-fade-configured-review-cycle event-fade-public-rss-review-cycle event-fade-gdelt-review-cycle event-fade-polymarket-review-cycle event-fade-no-key-review-cycle event-fade-merge-sample event-fade-export-outcome-prices event-fade-fill-outcomes status backup-db verify-restore maintenance rotate-logs launchd-status install-maintenance-agent restart-listener universe-audit refresh-universe-audit dry-run dry-run-fixture

help:
	@echo "Targets:"
	@echo "  make bootstrap  Create .venv and install requirements"
	@echo "  make export-src  Write a clean source zip using git archive"
	@echo "  make verify   Run the standard local verification suite"
	@echo "  make test     Run standalone tests"
	@echo "  make smoke-alerts  Render representative alerts without sending"
	@echo "  make backtest-fixture  Run offline backtest smoke from checked-in klines"
	@echo "  make backtest-costs  Run fixture backtest with costs + walk-forward"
	@echo "  make score    Print paper-trade scoreboard"
	@echo "  make score-json  Print paper-trade scoreboard as JSON"
	@echo "  make score-cohorts  Print paper-trade scoreboard with state cohorts"
	@echo "  make report   Print signal outcome report"
	@echo "  make event-fade-report  Score local event-fade fixtures"
	@echo "  make event-discovery-report  Print research-only event radar from fixtures"
	@echo "  make event-discovery-status  Print redacted event provider readiness"
	@echo "  make event-discovery-runs  Print recent cache refresh diagnostics"
	@echo "  make event-discovery-refresh  Write research-only event JSONL cache"
	@echo "  make event-discovery-refresh-configured  Cache configured event sources"
	@echo "  make event-discovery-refresh-public-rss  Cache no-key public RSS event evidence"
	@echo "  make event-discovery-refresh-gdelt  Cache no-key GDELT news event evidence"
	@echo "  make event-discovery-refresh-polymarket  Cache no-key Polymarket dated catalysts"
	@echo "  make event-discovery-binance-listen  Cache raw live Binance announcement evidence"
	@echo "  make event-llm-eval  Run offline LLM shadow eval fixtures"
	@echo "  make event-llm-extract-eval  Run offline LLM raw-extraction eval fixtures"
	@echo "  make event-alpha-eval  Run offline Event Alpha route/feedback eval fixtures"
	@echo "  make event-alpha-catalyst-frame-validation-cycle  Run offline LLM catalyst-frame validation fixtures"
	@echo "  make event-alpha-catalyst-frame-e2e-cycle  Run isolated AAVE/Kraken catalyst-frame e2e artifacts"
	@echo "  make event-alpha-notify-llm-quality-frame-smoke  Run notify_llm_quality-style fixture frame smoke, no sends"
	@echo "  make event-alpha-frame-quality-loop PROFILE=catalyst_frame_e2e  Run the full frame-quality artifact loop, no sends"
	@echo "  make event-alpha-signal-quality-eval  Run curated Event Alpha signal-quality benchmark fixtures"
	@echo "  make event-alpha-quality-review PROFILE=notify_llm  Review latest signal-quality artifact distribution"
	@echo "  make event-alpha-quality-coverage-report PROFILE=notify_llm_quality  Strictly check latest-run quality fields from raw artifacts"
	@echo "  make event-alpha-quality-validation-cycle  Offline no-send fixture cycle that writes/inspects signal-quality artifacts under the quality_validation namespace"
	@echo "  make event-alpha-notify-llm-quality-validation-cycle  Fresh notify_llm_quality no-send cycle with incidents, daily brief, and strict doctor"
	@echo "  make event-alpha-quality-live-smoke PROFILE=notify_llm_quality_fresh  Clean live-style no-send quality proof cycle plus reports"
	@echo "  make event-alpha-policy-simulate PROFILE=notify_llm  Simulate quality threshold policies without writes"
	@echo "  make event-alpha-export-signal-quality-cases PROFILE=notify_llm  Export proposed benchmark cases from artifacts"
	@echo "  make event-alpha-quality-loop PROFILE=notify_llm  Run the local signal-quality review chain (no sends)"
	@echo "  make event-opportunity-audit TARGET=ea:... PROFILE=notify_llm  Explain one candidate decision path"
	@echo "  make event-alpha-no-key-report  Print fixture market-anomaly event alpha radar"
	@echo "  make event-catalyst-search-fixture-report  Print fixture catalyst-search diagnostics for anomalies"
	@echo "  make event-alpha-cycle  Run one fixture Event Alpha research cycle"
	@echo "  make event-alpha-cycle-llm  Run one fixture Event Alpha cycle with fixture LLM metadata"
	@echo "  make event-alpha-cycle-search  Run one fixture Event Alpha cycle with catalyst search"
	@echo "  make event-alpha-cycle-search-llm  Run one fixture Event Alpha cycle with catalyst search and fixture LLM metadata"
	@echo "  make event-alpha-cycle-send  Run one Event Alpha cycle with opt-in research digest send flag"
	@echo "  Event Alpha cycles also emit impact_hypotheses/HYPOTHESIS rows and catalyst_search_skip_reasons for zero-query diagnostics"
	@echo "  make event-alpha-cycle-profile PROFILE=no_key_live  Run one Event Alpha cycle using an operational profile"
	@echo "  make event-alpha-cycle-profile-send PROFILE=research_send  Run a profiled cycle with the explicit send flag"
	@echo "  make event-alpha-notify-preview PROFILE=notify_no_key  Preview day-1 notification readiness, cooldowns, and provider backoff"
	@echo "  make event-alpha-notify-go-no-go PROFILE=notify_no_key  Summarize send go/no-go plus provider/reset/delivery/inbox commands"
	@echo "  make event-alpha-environment-doctor PROFILE=notify_no_key  Check scheduled notification environment and secrets readiness"
	@echo "  make event-alpha-scheduler-status PROFILE=notify_no_key  Check scheduled notification freshness, lock, and target status"
	@echo "  make event-alpha-notification-slo-report PROFILE=notify_no_key  Check notification SLO and delivery health"
	@echo "  make event-alpha-export-notification-pack PROFILE=notify_no_key  Write clean notification review zip"
	@echo "  make event-alpha-pause-notifications PROFILE=notify_no_key REASON='...'  Pause Telegram sends for this namespace"
	@echo "  make event-alpha-resume-notifications PROFILE=notify_no_key CONFIRM=1  Clear the namespace pause file"
	@echo "  make event-alpha-notification-checklist PROFILE=notify_no_key  Check preview/send readiness without sending"
	@echo "  make event-alpha-notify-no-key  Run day-1 no-key notification burn-in; sends only with RSI_EVENT_ALERTS_ENABLED=1"
	@echo "  make event-alpha-notify-llm  Run day-1 LLM notification burn-in; sends only with RSI_EVENT_ALERTS_ENABLED=1"
	@echo "  make event-alpha-notification-runs-report PROFILE=notify_no_key  Print notification summary rows"
	@echo "  make event-alpha-notification-inbox PROFILE=notify_no_key  Print unreviewed, partial-delivered, blocked, and would-send queues"
	@echo "  make event-alpha-notification-deliveries-report PROFILE=notify_no_key  Print delivery ledger states including partial/in-flight/blocked"
	@echo "  make event-alpha-notification-retry-failed PROFILE=notify_no_key  List failed deliveries (dry-run; CONFIRM=1 to proceed)"
	@echo "  make event-alpha-notify-no-key-scheduled  Scheduled no-key notify run (run lock + delivery ledger; sends only with RSI_EVENT_ALERTS_ENABLED=1)"
	@echo "  make event-alpha-notify-llm-scheduled  Scheduled LLM notify run (run lock + delivery ledger; sends only with RSI_EVENT_ALERTS_ENABLED=1)"
	@echo "  make event-alpha-notify-llm-deep-scheduled  Scheduled deeper bounded LLM notify run; sends only with RSI_EVENT_ALERTS_ENABLED=1"
	@echo "  make event-alpha-notify-llm-quality-scheduled  Fresh LLM quality artifact run under notify_llm_quality; no send flag"
	@echo "  make event-alpha-provider-health-report PROFILE=notify_no_key  Print profile provider health/backoff rows"
	@echo "  make event-alpha-provider-health-reset PROFILE=notify_no_key PROVIDER_KEY=gdelt:event_source CONFIRM=1  Clear selected provider backoff"
	@echo "  make event-alpha-notify-fixture-smoke  Run local fake-sender notification smoke"
	@echo "  make event-alpha-day1-start  Run no-send day-1 startup checks for notify_no_key"
	@echo "  Startup send commands after review: RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-send-test PROFILE=notify_no_key; RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-notify-no-key"
	@echo "  make event-alpha-send-test PROFILE=notify_no_key  Send one guarded research-only heartbeat"
	@echo "  make event-alpha-telegram-recipient-check PROFILE=notify_no_key  Send guarded per-recipient Telegram diagnostic"
	@echo "  make event-alpha-runs-report  Print Event Alpha cycle run ledger rows"
	@echo "  make event-impact-hypotheses-report PROFILE=notify_llm  Print latest-run Event Impact Hypothesis rows; add ALL_HISTORY=1 for full history"
	@echo "  make event-incidents-report PROFILE=notify_llm  Print canonical Event Alpha incident rows"
	@echo "  make event-impact-hypotheses-inbox PROFILE=notify_llm  Print Event Impact Hypothesis rows needing review"
	@echo "  make event-impact-hypothesis-smoke  Run offline SpaceX -> VELVET hypothesis validation smoke"
	@echo "  make event-alpha-status PROFILE=no_key_live  Print profile-aware Event Alpha readiness/status"
	@echo "  make event-alpha-daily-report  Run no-key daily status/cycle/runs/router/alerts report"
	@echo "  make event-alpha-daily-llm-report  Run full-LLM daily report profile without sending"
	@echo "  make event-alpha-daily-send  Run research-send profile; requires RSI_EVENT_ALERTS_ENABLED=1"
	@echo "  make event-alpha-health PROFILE=no_key_live  Print profile status, run ledger, and budget status"
	@echo "  make event-alpha-preflight PROFILE=no_key_live  Check profile paths, providers, LLM budget, and send guards"
	@echo "  make event-alpha-open-items  Print watchlist monitor, missed, and calibration open items"
	@echo "  make event-alpha-daily-brief  Write a Markdown daily Event Alpha brief"
	@echo "  make event-alpha-replay  Replay local Event Alpha artifacts without providers/sends"
	@echo "  make event-alpha-priors-shadow-report  Compare current alert tiers/scores before/after priors"
	@echo "  make event-alpha-burn-in-no-key  Daily no-key research burn-in: status, cycle, brief, explain"
	@echo "  make event-alpha-burn-in-llm  LLM research burn-in: status, cycle, brief, source reliability"
	@echo "  make event-alpha-weekly-review  Weekly outcomes/missed/calibration/reliability/priors review"
	@echo "  make event-alpha-burn-in-scorecard  Summarize burn-in runs, alerts, feedback, missed rows, health, and LLM budget"
	@echo "  make event-alpha-burn-in-checklist  Score readiness for research-send burn-in promotion"
	@echo "  make event-alpha-v1-readiness  Print v1 readiness gates for scheduled burn-in, research-send, and full LLM"
	@echo "  make event-alpha-health-guard PROFILE=no_key_live  Check run freshness, provider health, snapshots, and budget status"
	@echo "  make event-alpha-artifact-doctor PROFILE=no_key_live STRICT=1  Diagnose fresh artifact lineage and quality-route consistency"
	@echo "  INCLUDE_LEGACY=1 may be added to burn-in/readiness/doctor targets for migration review"
	@echo "  make event-alpha-tuning-worksheet  Print weekly tuning suggestions without applying changes"
	@echo "  make event-alpha-export-burn-in-pack  Write clean burn-in review zip"
	@echo "  make event-alpha-launchd-template  Print Event Alpha launchd/cron template locations"
	@echo "  make event-alpha-prune-artifacts CONFIRM=1  Prune old Event Alpha artifacts; dry-run by default"
	@echo "  make event-alpha-alerts-report  Print Event Alpha alert snapshot cohorts"
	@echo "  make event-alpha-fill-outcomes  Fill Event Alpha alert outcomes from local prices"
	@echo "  make event-watchlist-refresh  Refresh fixture event-alpha watchlist state"
	@echo "  make event-watchlist-report  Print latest event-alpha watchlist state"
	@echo "  make event-watchlist-monitor  Monitor active watchlist rows without new source evidence"
	@echo "  make event-alpha-router-report  Route latest watchlist state with daily/instant/triggered lanes"
	@echo "  make event-alpha-missed-report  Print missed-opportunity diagnostics"
	@echo "  make event-alpha-near-miss-report PROFILE=notify_llm_quality  Print near-promotion candidates and refresh diagnostics"
	@echo "  make event-alpha-calibration-report  Print calibration recommendations from artifacts"
	@echo "  make event-source-reliability-report  Print provider/source reliability recommendations"
	@echo "  make event-alpha-calibration-export-priors  Export reviewable calibration priors JSON"
	@echo "  make event-alpha-export-eval-cases  Export proposed eval cases from feedback and missed rows"
	@echo "  make event-alpha-explain-last-run  Explain why the latest Event Alpha run did/did not alert"
	@echo "  make event-research-cards ALERT_KEY=...  Print Markdown research card(s)"
	@echo "  make event-research-cards-write  Write research card markdown files and index"
	@echo "  make event-feedback-report  Print latest event-alpha feedback artifact"
	@echo "  make event-feedback-useful FEEDBACK_TARGET=...  Mark quick useful feedback"
	@echo "  make event-feedback-junk FEEDBACK_TARGET=...  Mark quick junk feedback"
	@echo "  make event-feedback-watch FEEDBACK_TARGET=...  Mark quick watch feedback"
	@echo "  make event-alert-no-key-report  Print no-key public-source event research alerts"
	@echo "  make event-alert-no-key-llm-report  Print no-key event alerts with LLM advisory metadata"
	@echo "  make event-alert-no-key-send  Send opt-in no-key event alert digest with LLM metadata"
	@echo "  make event-fade-auto-report  Print grouped event-fade discovery report"
	@echo "  make event-fade-export-sample  Write validation sample from fixtures"
	@echo "  make event-fade-export-cache-sample  Write validation sample from cache"
	@echo "  make event-fade-review-sample  Review status/labels/outcomes in validation sample"
	@echo "  make event-fade-labeling-queue  Prioritize validation rows to review"
	@echo "  make event-fade-review-packet  Write Markdown packet for manual validation review"
	@echo "  make event-fade-export-review-template  Write compact editable review sidecar"
	@echo "  make event-fade-apply-review-template  Apply edited review sidecar to sample"
	@echo "  make event-fade-check-review-template  Dry-check edited sidecar before applying"
	@echo "  make event-fade-check-review-bundle  Dry-check a bundle's balanced sidecar"
	@echo "  make event-fade-apply-review-bundle  Apply a bundle's balanced sidecar"
	@echo "  make event-fade-review-applied-bundle  Review a bundle's applied sample"
	@echo "  make event-fade-fill-review-bundle-outcomes  Fill outcomes for a bundle's applied sample"
	@echo "  make event-fade-review-bundle  Write manual review workspace"
	@echo "  make event-fade-cache-review-bundle  Write manual review workspace from cache"
	@echo "  make event-fade-review-cycle  Refresh research cache and write review workspace"
	@echo "  make event-fade-configured-review-cycle  Refresh configured sources and write review workspace"
	@echo "  make event-fade-public-rss-review-cycle  Refresh public RSS sources and write review workspace"
	@echo "  make event-fade-gdelt-review-cycle  Refresh GDELT news sources and write review workspace"
	@echo "  make event-fade-polymarket-review-cycle  Refresh Polymarket catalysts and write review workspace"
	@echo "  make event-fade-no-key-review-cycle  Refresh public RSS + GDELT + Polymarket and write review workspace"
	@echo "  make event-fade-merge-sample  Preserve review status/labels/outcomes in fresh sample"
	@echo "  make event-fade-export-outcome-prices  Build local validation price fixture"
	@echo "  make event-fade-fill-outcomes  Fill validation outcomes from local prices"
	@echo "  make status   Print operational scan/listener health"
	@echo "  make backup-db  Create and verify a SQLite backup"
	@echo "  make verify-restore  Restore-check the newest SQLite backup"
	@echo "  make maintenance  Run backup, restore drill, and log rotation"
	@echo "  make rotate-logs  Rotate oversized scan/listener logs"
	@echo "  make launchd-status  Print scan/listener launchd status"
	@echo "  make install-maintenance-agent  Install/load daily maintenance LaunchAgent"
	@echo "  make restart-listener  Restart the always-on bot listener"
	@echo "  make universe-audit  Print latest universe hygiene audit"
	@echo "  make refresh-universe-audit  Fetch and persist a fresh hygiene audit"
	@echo "  make dry-run  Run a small network dry scan without writes/alerts"
	@echo "  make dry-run-fixture  Run a small offline dry scan from checked-in fixtures"

check-python:
	@if ! test -x "$(PYTHON)" && ! command -v "$(PYTHON)" >/dev/null 2>&1; then \
		echo "Python runtime '$(PYTHON)' not found."; \
		echo "Run 'make bootstrap' or override with 'make verify PYTHON=python3'."; \
		exit 127; \
	fi

bootstrap:
	python3 -m venv .venv
	.venv/bin/python -m pip install -r requirements.txt

export-src:
	git archive --format=zip -o crypto-rsi-scanner-source.zip HEAD

verify: check-python test smoke-alerts backtest-fixture score

test:
	$(PYTHON) tests/test_indicators.py

smoke-alerts:
	$(PYTHON) -m crypto_rsi_scanner.alert_smoke

backtest-fixture:
	$(PYTHON) -m crypto_rsi_scanner.backtest --fixture-dir fixtures/backtest_smoke --top-n 3 --days 365 --min-signals 1

backtest-costs:
	$(PYTHON) -m crypto_rsi_scanner.backtest --fixture-dir fixtures/backtest_smoke --top-n 3 --days 365 --state-slices --costs --walk-forward --min-signals 1

score:
	$(PYTHON) main.py --score

score-json:
	$(PYTHON) main.py --score --json

score-cohorts:
	$(PYTHON) main.py --score --cohorts

report:
	$(PYTHON) main.py --report

event-fade-report:
	env $(EVENT_FIXTURE_NOW_ENV) \
	$(PYTHON) main.py --event-fade-report

event-discovery-report:
	env $(EVENT_FIXTURE_NOW_ENV) \
	RSI_EVENT_DISCOVERY_EVENTS_PATH=fixtures/event_discovery/raw_events.json \
	RSI_EVENT_DISCOVERY_ALIASES_PATH=fixtures/event_discovery/asset_aliases.json \
	RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH=fixtures/event_discovery/binance_announcements.json \
	RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH=fixtures/event_discovery/bybit_announcements.json \
	RSI_EVENT_DISCOVERY_COINMARKETCAL_PATH=fixtures/event_discovery/coinmarketcal_events.json \
	RSI_EVENT_DISCOVERY_TOKENOMIST_PATH=fixtures/event_discovery/tokenomist_unlocks.json \
	RSI_EVENT_DISCOVERY_CRYPTOPANIC_PATH=fixtures/event_discovery/cryptopanic_news.json \
	RSI_EVENT_DISCOVERY_GDELT_PATH=fixtures/event_discovery/gdelt_news.json \
	RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH=fixtures/event_discovery/project_blog_rss.json \
	RSI_EVENT_DISCOVERY_EXTERNAL_IPO_PATH=fixtures/event_discovery/external_ipo_events.json \
	RSI_EVENT_DISCOVERY_SPORTS_FIXTURES_PATH=fixtures/event_discovery/sports_fixtures.json \
	RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH=fixtures/event_discovery/prediction_market_events.json \
	RSI_EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH=fixtures/event_discovery/coinalyze_derivatives.json \
	RSI_EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH=fixtures/event_discovery/tokenomist_supply.json \
	RSI_EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH=fixtures/event_discovery/etherscan_supply.json \
	RSI_EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH=fixtures/event_discovery/arkham_supply.json \
	RSI_EVENT_DISCOVERY_DUNE_SUPPLY_PATH=fixtures/event_discovery/dune_supply.json \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=fixtures/coingecko_smoke/top_markets.json \
	RSI_EVENT_DISCOVERY_LOOKBACK_HOURS=120 \
	RSI_EVENT_DISCOVERY_HORIZON_DAYS=2 \
	$(PYTHON) main.py --event-discovery-report

event-discovery-status:
	$(PYTHON) main.py --event-discovery-status

event-discovery-runs:
	RSI_EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) \
	$(PYTHON) main.py --event-discovery-runs

event-discovery-refresh:
	RSI_EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) \
	env $(EVENT_FIXTURE_NOW_ENV) \
	RSI_EVENT_DISCOVERY_EVENTS_PATH=fixtures/event_discovery/raw_events.json \
	RSI_EVENT_DISCOVERY_ALIASES_PATH=fixtures/event_discovery/asset_aliases.json \
	RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH=fixtures/event_discovery/binance_announcements.json \
	RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH=fixtures/event_discovery/bybit_announcements.json \
	RSI_EVENT_DISCOVERY_COINMARKETCAL_PATH=fixtures/event_discovery/coinmarketcal_events.json \
	RSI_EVENT_DISCOVERY_TOKENOMIST_PATH=fixtures/event_discovery/tokenomist_unlocks.json \
	RSI_EVENT_DISCOVERY_CRYPTOPANIC_PATH=fixtures/event_discovery/cryptopanic_news.json \
	RSI_EVENT_DISCOVERY_GDELT_PATH=fixtures/event_discovery/gdelt_news.json \
	RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH=fixtures/event_discovery/project_blog_rss.json \
	RSI_EVENT_DISCOVERY_EXTERNAL_IPO_PATH=fixtures/event_discovery/external_ipo_events.json \
	RSI_EVENT_DISCOVERY_SPORTS_FIXTURES_PATH=fixtures/event_discovery/sports_fixtures.json \
	RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH=fixtures/event_discovery/prediction_market_events.json \
	RSI_EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH=fixtures/event_discovery/coinalyze_derivatives.json \
	RSI_EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH=fixtures/event_discovery/tokenomist_supply.json \
	RSI_EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH=fixtures/event_discovery/etherscan_supply.json \
	RSI_EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH=fixtures/event_discovery/arkham_supply.json \
	RSI_EVENT_DISCOVERY_DUNE_SUPPLY_PATH=fixtures/event_discovery/dune_supply.json \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=fixtures/coingecko_smoke/top_markets.json \
	RSI_EVENT_DISCOVERY_LOOKBACK_HOURS=120 \
	RSI_EVENT_DISCOVERY_HORIZON_DAYS=2 \
	$(PYTHON) main.py --event-discovery-refresh

event-discovery-refresh-configured:
	RSI_EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) \
	$(PYTHON) main.py --event-discovery-refresh

event-discovery-refresh-public-rss:
	RSI_EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) \
	RSI_EVENT_DISCOVERY_LOOKBACK_HOURS=$(EVENT_DISCOVERY_RSS_LOOKBACK_HOURS) \
	RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=1 \
	RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH=$(EVENT_DISCOVERY_RSS_URLS_PATH) \
	RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=$(EVENT_DISCOVERY_RSS_UNIVERSE_LIVE) \
	RSI_EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT=$(EVENT_DISCOVERY_RSS_UNIVERSE_FETCH_LIMIT) \
	$(PYTHON) main.py --event-discovery-refresh

event-discovery-refresh-gdelt:
	RSI_EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) \
	RSI_EVENT_DISCOVERY_LOOKBACK_HOURS=$(EVENT_DISCOVERY_GDELT_LOOKBACK_HOURS) \
	RSI_EVENT_DISCOVERY_GDELT_LIVE=1 \
	RSI_EVENT_DISCOVERY_GDELT_QUERY='$(EVENT_DISCOVERY_GDELT_QUERY)' \
	RSI_EVENT_DISCOVERY_GDELT_MAX_RECORDS=$(EVENT_DISCOVERY_GDELT_MAX_RECORDS) \
	RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=$(EVENT_DISCOVERY_GDELT_UNIVERSE_LIVE) \
	RSI_EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT=$(EVENT_DISCOVERY_GDELT_UNIVERSE_FETCH_LIMIT) \
	$(PYTHON) main.py --event-discovery-refresh

event-discovery-refresh-polymarket:
	RSI_EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) \
	RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE=1 \
	RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT=$(EVENT_DISCOVERY_POLYMARKET_LIMIT) \
	RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=$(EVENT_DISCOVERY_POLYMARKET_UNIVERSE_LIVE) \
	RSI_EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT=$(EVENT_DISCOVERY_POLYMARKET_UNIVERSE_FETCH_LIMIT) \
	$(PYTHON) main.py --event-discovery-refresh

event-discovery-binance-listen:
	RSI_EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) \
	$(PYTHON) main.py --event-discovery-binance-listen

event-llm-eval:
	$(PYTHON) -m crypto_rsi_scanner.event_llm_eval fixtures/event_discovery/llm_golden_cases.json

event-llm-extract-eval:
	$(PYTHON) -m crypto_rsi_scanner.event_llm_extract_eval fixtures/event_discovery/llm_extraction_golden_cases.json

event-alpha-eval:
	$(PYTHON) -m crypto_rsi_scanner.event_alpha_eval fixtures/event_discovery/event_alpha_golden_cases.json

event-alpha-catalyst-frame-validation-cycle: PROFILE = catalyst_frame_validation
event-alpha-catalyst-frame-validation-cycle:
	rm -rf event_fade_cache/$(PROFILE)
	$(PYTHON) -m crypto_rsi_scanner.event_llm_catalyst_frames_eval fixtures/event_discovery/llm_catalyst_frame_cases.json
	$(EVENT_FIXTURE_NOW_ENV) $(PYTHON) main.py --event-alpha-cycle --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-daily-brief --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) --event-alpha-include-test-artifacts
	$(PYTHON) main.py --event-alpha-quality-review --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-artifact-doctor --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) --event-alpha-include-test-artifacts --event-alpha-artifact-doctor-strict
	@echo "Catalyst-frame validation artifacts under event_fade_cache/$(PROFILE)/."

event-alpha-catalyst-frame-e2e-cycle: PROFILE = catalyst_frame_e2e
event-alpha-catalyst-frame-e2e-cycle:
	rm -rf event_fade_cache/$(PROFILE)
	$(PYTHON) -m crypto_rsi_scanner.event_llm_catalyst_frames_eval fixtures/event_discovery/llm_catalyst_frame_cases.json
	$(EVENT_FIXTURE_NOW_ENV) $(PYTHON) main.py --event-alpha-cycle --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-daily-brief --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) --event-alpha-include-test-artifacts
	$(PYTHON) main.py --event-impact-hypotheses-report --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-incidents-report --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-quality-review --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-artifact-doctor --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) --event-alpha-include-test-artifacts --event-alpha-artifact-doctor-strict
	@echo "Catalyst-frame e2e artifacts under event_fade_cache/$(PROFILE)/."

event-alpha-notify-llm-quality-frame-smoke: PROFILE = notify_llm_quality_frame
event-alpha-notify-llm-quality-frame-smoke:
	rm -rf event_fade_cache/$(PROFILE)
	$(PYTHON) -m crypto_rsi_scanner.event_llm_catalyst_frames_eval fixtures/event_discovery/llm_catalyst_frame_cases.json
	$(EVENT_FIXTURE_NOW_ENV) $(PYTHON) main.py --event-alpha-cycle --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-daily-brief --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) --event-alpha-include-test-artifacts
	$(PYTHON) main.py --event-impact-hypotheses-report --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-incidents-report --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-quality-review --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-artifact-doctor --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) --event-alpha-include-test-artifacts --event-alpha-artifact-doctor-strict
	@echo "Notify LLM quality frame smoke artifacts under event_fade_cache/$(PROFILE)/."

event-alpha-frame-quality-loop: PROFILE = catalyst_frame_e2e
event-alpha-frame-quality-loop: TARGET = AAVE
event-alpha-frame-quality-loop:
	$(MAKE) event-alpha-signal-quality-eval PYTHON=$(PYTHON)
	$(MAKE) event-alpha-catalyst-frame-e2e-cycle PROFILE=$(PROFILE) PYTHON=$(PYTHON)
	$(MAKE) event-alpha-quality-review PROFILE=$(PROFILE) PYTHON=$(PYTHON)
	$(MAKE) event-incidents-report PROFILE=$(PROFILE) PYTHON=$(PYTHON)
	$(MAKE) event-impact-hypotheses-report PROFILE=$(PROFILE) PYTHON=$(PYTHON)
	$(MAKE) event-alpha-daily-brief PROFILE=$(PROFILE) PYTHON=$(PYTHON)
	$(MAKE) event-alpha-artifact-doctor PROFILE=$(PROFILE) STRICT=1 PYTHON=$(PYTHON)
	$(MAKE) event-opportunity-audit PROFILE=$(PROFILE) TARGET=$(TARGET) PYTHON=$(PYTHON)
	@echo "Frame-quality loop completed for event_fade_cache/$(PROFILE)/; audit target=$(TARGET)."

event-alpha-signal-quality-eval:
	$(PYTHON) main.py --event-alpha-signal-quality-eval

event-alpha-quality-review: PROFILE = notify_llm
event-alpha-quality-review:
	$(PYTHON) main.py --event-alpha-quality-review --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)

event-alpha-quality-coverage-report: PROFILE = notify_llm_quality
event-alpha-quality-coverage-report:
	$(PYTHON) main.py --event-alpha-quality-coverage-report --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)

# Reproducible offline validation of the signal-quality layer in an isolated
# namespace. No Telegram sends, no live providers; fixture sources + fixture clock.
# Writes run ledger, impact hypotheses, watchlist, alert snapshots (if any),
# research cards, and daily brief under event_fade_cache/quality_validation/.
event-alpha-quality-validation-cycle: PROFILE = quality_validation
event-alpha-quality-validation-cycle:
	@if [ "$(PROFILE)" = "quality_validation" ]; then rm -rf event_fade_cache/$(PROFILE); fi
	$(EVENT_FIXTURE_NOW_ENV) $(PYTHON) main.py --event-alpha-cycle --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-daily-brief --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) --event-alpha-include-test-artifacts
	$(PYTHON) main.py --event-alpha-quality-review --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-artifact-doctor --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) --event-alpha-include-test-artifacts --event-alpha-artifact-doctor-strict
	@echo "Validation artifacts under event_fade_cache/$(PROFILE)/. Inspect with:"
	@echo "  make event-impact-hypotheses-report PROFILE=$(PROFILE)"
	@echo "  make event-opportunity-audit TARGET=<symbol|hypothesis_id|alert_id> PROFILE=$(PROFILE)"

event-alpha-notify-llm-quality-validation-cycle: PROFILE = notify_llm_quality
event-alpha-notify-llm-quality-validation-cycle:
	rm -rf event_fade_cache/$(PROFILE)
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	RSI_EVENT_ALPHA_NOTIFY_LOCK_ENABLED=0 \
	RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT=0 \
	RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_WINDOW_HOURS=0 \
	$(PYTHON) main.py --event-alpha-notify-cycle --event-alpha-profile $(PROFILE)
	$(PYTHON) main.py --event-alpha-daily-brief --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-quality-review --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-incidents-report --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-artifact-doctor --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) --event-alpha-artifact-doctor-strict
	@echo "Notify LLM quality artifacts under event_fade_cache/$(PROFILE)/. No Telegram send is requested."

event-alpha-notify-llm-quality-fresh-cycle: PROFILE = notify_llm_quality_fresh
event-alpha-notify-llm-quality-fresh-cycle:
	rm -rf event_fade_cache/$(PROFILE)
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	RSI_EVENT_ALPHA_NOTIFY_LOCK_ENABLED=0 \
	RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT=0 \
	RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_WINDOW_HOURS=0 \
	$(PYTHON) main.py --event-alpha-notify-cycle --event-alpha-profile $(PROFILE)
	$(PYTHON) main.py --event-alpha-daily-brief --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-quality-review --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-incidents-report --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)
	$(PYTHON) main.py --event-alpha-artifact-doctor --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) --event-alpha-artifact-doctor-strict
	@echo "Fresh live-style quality artifacts under event_fade_cache/$(PROFILE)/. No Telegram send is requested."

event-alpha-quality-live-smoke: PROFILE = notify_llm_quality_fresh
event-alpha-quality-live-smoke:
	$(MAKE) event-alpha-notify-llm-quality-fresh-cycle PROFILE=$(PROFILE) PYTHON=$(PYTHON)

event-alpha-policy-simulate: PROFILE = notify_llm
event-alpha-policy-simulate:
	$(PYTHON) main.py --event-alpha-policy-simulate --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)

event-alpha-export-signal-quality-cases: PROFILE = notify_llm
event-alpha-export-signal-quality-cases:
	$(PYTHON) main.py --event-alpha-export-signal-quality-cases --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE)

event-alpha-quality-loop: PROFILE = notify_llm
event-alpha-quality-loop:
	$(MAKE) event-alpha-signal-quality-eval PYTHON=$(PYTHON)
	$(MAKE) event-alpha-quality-review PROFILE=$(PROFILE) PYTHON=$(PYTHON)
	$(MAKE) event-alpha-policy-simulate PROFILE=$(PROFILE) PYTHON=$(PYTHON)
	$(MAKE) event-alpha-notification-inbox PROFILE=$(PROFILE) PYTHON=$(PYTHON)
	$(MAKE) event-impact-hypotheses-report PROFILE=$(PROFILE) PYTHON=$(PYTHON)
	$(MAKE) event-alpha-daily-brief PROFILE=$(PROFILE) PYTHON=$(PYTHON)

event-alpha-quality-loop-llm:
	$(MAKE) event-alpha-quality-loop PROFILE=notify_llm PYTHON=$(PYTHON)

event-opportunity-audit: PROFILE = notify_llm
event-opportunity-audit:
	@if [ -z "$(TARGET)" ]; then echo "Set TARGET=ea:... or TARGET=SYMBOL"; exit 2; fi
	$(PYTHON) main.py --event-opportunity-audit "$(TARGET)" --event-alpha-profile $(PROFILE)

event-alpha-no-key-report:
	env $(EVENT_FIXTURE_NOW_ENV) \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_MARKET_ENRICHMENT_ENABLED=1 \
	RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 \
	RSI_EVENT_ANOMALY_MIN_RETURN_24H=$(EVENT_ALPHA_ANOMALY_MIN_RETURN_24H) \
	RSI_EVENT_ANOMALY_MIN_VOLUME_MCAP=$(EVENT_ALPHA_ANOMALY_MIN_VOLUME_MCAP) \
	$(PYTHON) main.py --event-alpha-radar-report

event-catalyst-search-fixture-report:
	env $(EVENT_FIXTURE_NOW_ENV) \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_MARKET_ENRICHMENT_ENABLED=1 \
	RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 \
	RSI_EVENT_ANOMALY_MIN_RETURN_24H=$(EVENT_ALPHA_ANOMALY_MIN_RETURN_24H) \
	RSI_EVENT_ANOMALY_MIN_VOLUME_MCAP=$(EVENT_ALPHA_ANOMALY_MIN_VOLUME_MCAP) \
	RSI_EVENT_CATALYST_SEARCH_ENABLED=1 \
	RSI_EVENT_CATALYST_SEARCH_PROVIDER=fixture \
	RSI_EVENT_CATALYST_SEARCH_FIXTURE_PATH=$(EVENT_CATALYST_SEARCH_FIXTURE_PATH) \
	$(PYTHON) main.py --event-catalyst-search-report

event-alpha-cycle:
	env $(EVENT_FIXTURE_NOW_ENV) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=fixture \
	RSI_EVENT_ALPHA_RUN_MODE=fixture \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_MARKET_ENRICHMENT_ENABLED=1 \
	RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 \
	RSI_EVENT_ANOMALY_MIN_RETURN_24H=$(EVENT_ALPHA_ANOMALY_MIN_RETURN_24H) \
	RSI_EVENT_ANOMALY_MIN_VOLUME_MCAP=$(EVENT_ALPHA_ANOMALY_MIN_VOLUME_MCAP) \
	RSI_EVENT_WATCHLIST_ENABLED=1 \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_watchlist_state.jsonl \
	RSI_EVENT_ALPHA_ROUTER_ENABLED=1 \
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_alpha_alerts.jsonl \
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_alpha_runs.jsonl \
	$(PYTHON) main.py --event-alpha-cycle

event-alpha-cycle-llm:
	env $(EVENT_FIXTURE_NOW_ENV) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=fixture \
	RSI_EVENT_ALPHA_RUN_MODE=fixture \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_MARKET_ENRICHMENT_ENABLED=1 \
	RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 \
	RSI_EVENT_ANOMALY_MIN_RETURN_24H=$(EVENT_ALPHA_ANOMALY_MIN_RETURN_24H) \
	RSI_EVENT_ANOMALY_MIN_VOLUME_MCAP=$(EVENT_ALPHA_ANOMALY_MIN_VOLUME_MCAP) \
	RSI_EVENT_WATCHLIST_ENABLED=1 \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_watchlist_state.jsonl \
	RSI_EVENT_ALPHA_ROUTER_ENABLED=1 \
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_alpha_alerts.jsonl \
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_alpha_runs.jsonl \
	RSI_EVENT_LLM_MODE=$(EVENT_ALERT_LLM_MODE) \
	RSI_EVENT_LLM_PROVIDER=$(EVENT_ALERT_LLM_PROVIDER) \
	RSI_EVENT_LLM_EXTRACTOR_MODE=advisory \
	RSI_EVENT_LLM_EXTRACTOR_PROVIDER=$(EVENT_ALERT_LLM_PROVIDER) \
	$(PYTHON) main.py --event-alpha-cycle --with-llm

event-alpha-cycle-search:
	env $(EVENT_FIXTURE_NOW_ENV) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=fixture \
	RSI_EVENT_ALPHA_RUN_MODE=fixture \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_MARKET_ENRICHMENT_ENABLED=1 \
	RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 \
	RSI_EVENT_ANOMALY_MIN_RETURN_24H=$(EVENT_ALPHA_ANOMALY_MIN_RETURN_24H) \
	RSI_EVENT_ANOMALY_MIN_VOLUME_MCAP=$(EVENT_ALPHA_ANOMALY_MIN_VOLUME_MCAP) \
	RSI_EVENT_CATALYST_SEARCH_ENABLED=1 \
	RSI_EVENT_CATALYST_SEARCH_PROVIDER=fixture \
	RSI_EVENT_CATALYST_SEARCH_FIXTURE_PATH=$(EVENT_CATALYST_SEARCH_FIXTURE_PATH) \
	RSI_EVENT_WATCHLIST_ENABLED=1 \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_watchlist_state.jsonl \
	RSI_EVENT_ALPHA_ROUTER_ENABLED=1 \
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_alpha_alerts.jsonl \
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_alpha_runs.jsonl \
	$(PYTHON) main.py --event-alpha-cycle

event-alpha-cycle-search-llm:
	env $(EVENT_FIXTURE_NOW_ENV) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=fixture \
	RSI_EVENT_ALPHA_RUN_MODE=fixture \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_MARKET_ENRICHMENT_ENABLED=1 \
	RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 \
	RSI_EVENT_ANOMALY_MIN_RETURN_24H=$(EVENT_ALPHA_ANOMALY_MIN_RETURN_24H) \
	RSI_EVENT_ANOMALY_MIN_VOLUME_MCAP=$(EVENT_ALPHA_ANOMALY_MIN_VOLUME_MCAP) \
	RSI_EVENT_CATALYST_SEARCH_ENABLED=1 \
	RSI_EVENT_CATALYST_SEARCH_PROVIDER=fixture \
	RSI_EVENT_CATALYST_SEARCH_FIXTURE_PATH=$(EVENT_CATALYST_SEARCH_FIXTURE_PATH) \
	RSI_EVENT_WATCHLIST_ENABLED=1 \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_watchlist_state.jsonl \
	RSI_EVENT_ALPHA_ROUTER_ENABLED=1 \
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_alpha_alerts.jsonl \
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_alpha_runs.jsonl \
	RSI_EVENT_LLM_MODE=$(EVENT_ALERT_LLM_MODE) \
	RSI_EVENT_LLM_PROVIDER=$(EVENT_ALERT_LLM_PROVIDER) \
	RSI_EVENT_LLM_EXTRACTOR_MODE=advisory \
	RSI_EVENT_LLM_EXTRACTOR_PROVIDER=$(EVENT_ALERT_LLM_PROVIDER) \
	$(PYTHON) main.py --event-alpha-cycle --with-llm

event-alpha-cycle-send:
	env $(EVENT_FIXTURE_NOW_ENV) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=fixture \
	RSI_EVENT_ALPHA_RUN_MODE=fixture \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_MARKET_ENRICHMENT_ENABLED=1 \
	RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 \
	RSI_EVENT_ANOMALY_MIN_RETURN_24H=$(EVENT_ALPHA_ANOMALY_MIN_RETURN_24H) \
	RSI_EVENT_ANOMALY_MIN_VOLUME_MCAP=$(EVENT_ALPHA_ANOMALY_MIN_VOLUME_MCAP) \
	RSI_EVENT_WATCHLIST_ENABLED=1 \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_watchlist_state.jsonl \
	RSI_EVENT_ALPHA_ROUTER_ENABLED=1 \
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_alpha_alerts.jsonl \
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_FIXTURE_DIR)/event_alpha_runs.jsonl \
	RSI_EVENT_LLM_MODE=$(EVENT_ALERT_LLM_MODE) \
	RSI_EVENT_LLM_PROVIDER=$(EVENT_ALERT_LLM_PROVIDER) \
	RSI_EVENT_LLM_EXTRACTOR_MODE=advisory \
	RSI_EVENT_LLM_EXTRACTOR_PROVIDER=$(EVENT_ALERT_LLM_PROVIDER) \
	$(PYTHON) main.py --event-alpha-cycle --with-llm --event-alert-send

event-alpha-cycle-profile:
	env $(EVENT_RESEARCH_NOW_ENV) \
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-cycle --event-alpha-profile $(PROFILE)

event-alpha-cycle-profile-send:
	env $(EVENT_RESEARCH_NOW_ENV) \
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-cycle --event-alpha-profile $(PROFILE) --event-alert-send

event-alpha-notify-cycle:
	env $(EVENT_RESEARCH_NOW_ENV) \
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-notify-cycle --event-alpha-profile $(PROFILE) --event-alert-send $(EVENT_ALPHA_IGNORE_BACKOFF_ARG)

event-alpha-notify-no-key: PROFILE = notify_no_key
event-alpha-notify-no-key: event-alpha-notify-cycle

event-alpha-notify-llm: PROFILE = notify_llm
event-alpha-notify-llm: event-alpha-notify-cycle

event-alpha-notify-preview: PROFILE = notify_no_key
event-alpha-notify-preview:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-notify-preview --event-alpha-profile $(PROFILE)

event-alpha-notify-go-no-go: PROFILE = notify_no_key
event-alpha-notify-go-no-go:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-notify-go-no-go --event-alpha-profile $(PROFILE)

event-alpha-environment-doctor: PROFILE = notify_no_key
event-alpha-environment-doctor:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-environment-doctor --event-alpha-profile $(PROFILE)

event-alpha-pause-notifications: PROFILE = notify_no_key
event-alpha-pause-notifications:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-pause-notifications --event-alpha-profile $(PROFILE) $(if $(strip $(REASON)),--reason "$(REASON)",)

event-alpha-resume-notifications: PROFILE = notify_no_key
event-alpha-resume-notifications:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-resume-notifications --event-alpha-profile $(PROFILE) $(if $(filter 1 true yes,$(CONFIRM)),--confirm,)

event-alpha-scheduler-status: PROFILE = notify_no_key
event-alpha-scheduler-status:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-scheduler-status --event-alpha-profile $(PROFILE)

event-alpha-generate-launchd: PROFILE = notify_no_key
event-alpha-generate-launchd:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-generate-launchd --event-alpha-profile $(PROFILE) --out $(EVENT_ALPHA_LAUNCHD_OUT)

event-alpha-notification-slo-report: PROFILE = notify_no_key
event-alpha-notification-slo-report:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-notification-slo-report --event-alpha-profile $(PROFILE)

event-alpha-export-notification-pack: PROFILE = notify_no_key
event-alpha-export-notification-pack:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-export-notification-pack --event-alpha-profile $(PROFILE) --out $(EVENT_ALPHA_NOTIFICATION_PACK)

event-alpha-notification-checklist: PROFILE = notify_no_key
event-alpha-notification-checklist:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	RSI_EVENT_ALPHA_NOTIFICATION_RUNS_PATH=$(EVENT_ALPHA_NOTIFICATION_RUNS_PATH) \
	$(PYTHON) main.py --event-alpha-notification-checklist --event-alpha-profile $(PROFILE)

event-alpha-send-test: PROFILE = notify_no_key
event-alpha-send-test:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-send-test --event-alpha-profile $(PROFILE)

event-alpha-telegram-recipient-check: PROFILE = notify_no_key
event-alpha-telegram-recipient-check:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-telegram-recipient-check --event-alpha-profile $(PROFILE)

event-alpha-notification-runs-report:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-notification-runs-report --event-alpha-profile $(PROFILE) --event-alpha-run-limit 20

event-alpha-notification-inbox: PROFILE = notify_no_key
event-alpha-notification-inbox:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-notification-inbox --event-alpha-profile $(PROFILE)

event-alpha-notification-deliveries-report: PROFILE = notify_no_key
event-alpha-notification-deliveries-report:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-notification-deliveries-report --event-alpha-profile $(PROFILE)

event-alpha-notification-retry-failed: PROFILE = notify_no_key
event-alpha-notification-retry-failed:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-notification-retry-failed --event-alpha-profile $(PROFILE) $(if $(filter 1 true yes,$(CONFIRM)),--confirm,)

# Scheduled day-1 notification runs. Research-only: sends only with
# RSI_EVENT_ALERTS_ENABLED=1 + Telegram config. They use the per-profile run lock
# and delivery ledger, use real wall-clock time (no fixed research clock), fail
# soft on provider errors (exit 0 on partial failure), and never paper/live trade
# or write normal RSI rows. The notify_no_key/notify_llm notification profiles
# intentionally send operator-visible output on every clean run, so content
# dedupe is disabled while overlap/in-flight safety remains in place.
event-alpha-notify-no-key-scheduled: PROFILE = notify_no_key
event-alpha-notify-llm-scheduled: PROFILE = notify_llm
event-alpha-notify-llm-deep-scheduled: PROFILE = notify_llm_deep
event-alpha-notify-no-key-scheduled event-alpha-notify-llm-scheduled event-alpha-notify-llm-deep-scheduled:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	RSI_EVENT_ALPHA_NOTIFY_LOCK_ENABLED=1 \
	RSI_EVENT_ALPHA_NOTIFY_ALLOW_OVERLAP=0 \
	RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT=$(EVENT_ALPHA_NOTIFY_DEDUPE_BY_CONTENT) \
	RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_WINDOW_HOURS=$(EVENT_ALPHA_NOTIFY_DEDUPE_WINDOW_HOURS) \
	$(PYTHON) main.py --event-alpha-notify-cycle --event-alpha-profile $(PROFILE) --event-alert-send
	@echo "Next: make event-alpha-notification-deliveries-report PROFILE=$(PROFILE)"
	@echo "Next: make event-alpha-notification-runs-report PROFILE=$(PROFILE)   # notify lock/delivery summary per run"

event-alpha-notify-llm-quality-scheduled: PROFILE = notify_llm_quality
event-alpha-notify-llm-quality-scheduled:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	RSI_EVENT_ALPHA_NOTIFY_LOCK_ENABLED=1 \
	RSI_EVENT_ALPHA_NOTIFY_ALLOW_OVERLAP=0 \
	RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT=0 \
	RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_WINDOW_HOURS=0 \
	$(PYTHON) main.py --event-alpha-notify-cycle --event-alpha-profile $(PROFILE)
	@echo "Next: make event-alpha-quality-coverage-report PROFILE=$(PROFILE)"
	@echo "Next: make event-alpha-artifact-doctor PROFILE=$(PROFILE) STRICT=1"

event-alpha-provider-health-report: PROFILE = notify_no_key
event-alpha-provider-health-report:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-provider-health-report --event-alpha-profile $(PROFILE)

event-alpha-provider-health-reset: PROFILE = notify_no_key
event-alpha-provider-health-reset:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-provider-health-reset --event-alpha-profile $(PROFILE) $(EVENT_ALPHA_PROVIDER_SELECTOR_ARGS) $(if $(filter 1 true yes,$(CONFIRM)),--confirm,)

event-alpha-notify-fixture-smoke:
	env $(EVENT_FIXTURE_NOW_ENV) \
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=fixture_notify_smoke \
	$(PYTHON) main.py --event-alpha-notify-fixture-smoke

event-alpha-day1-start: PROFILE = notify_no_key
event-alpha-day1-start:
	$(MAKE) event-alpha-preflight PROFILE=notify_no_key PYTHON=$(PYTHON)
	$(MAKE) event-alpha-notification-checklist PROFILE=notify_no_key PYTHON=$(PYTHON)
	$(MAKE) event-alpha-notify-preview PROFILE=notify_no_key PYTHON=$(PYTHON)
	@echo "Next guarded send commands after review:"
	@echo "  RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-send-test PROFILE=notify_no_key"
	@echo "  RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-notify-no-key"

event-alpha-day1-start-llm: PROFILE = notify_llm
event-alpha-day1-start-llm:
	$(MAKE) event-alpha-preflight PROFILE=notify_llm PYTHON=$(PYTHON)
	$(MAKE) event-alpha-notification-checklist PROFILE=notify_llm PYTHON=$(PYTHON)
	$(MAKE) event-alpha-notify-preview PROFILE=notify_llm PYTHON=$(PYTHON)
	@echo "Next guarded send commands after review:"
	@echo "  RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-send-test PROFILE=notify_llm"
	@echo "  RSI_EVENT_ALERTS_ENABLED=1 make event-alpha-notify-llm"

event-alpha-notify-start-no-key:
	$(MAKE) event-alpha-preflight PROFILE=notify_no_key PYTHON=$(PYTHON)
	$(MAKE) event-alpha-notification-checklist PROFILE=notify_no_key PYTHON=$(PYTHON)
	RSI_EVENT_ALERTS_ENABLED=1 $(MAKE) event-alpha-send-test PROFILE=notify_no_key PYTHON=$(PYTHON)
	RSI_EVENT_ALERTS_ENABLED=1 $(MAKE) event-alpha-notify-no-key PYTHON=$(PYTHON)

event-alpha-notify-start-llm:
	$(MAKE) event-alpha-preflight PROFILE=notify_llm PYTHON=$(PYTHON)
	$(MAKE) event-alpha-notification-checklist PROFILE=notify_llm PYTHON=$(PYTHON)
	RSI_EVENT_ALERTS_ENABLED=1 $(MAKE) event-alpha-send-test PROFILE=notify_llm PYTHON=$(PYTHON)
	RSI_EVENT_ALERTS_ENABLED=1 $(MAKE) event-alpha-notify-llm PYTHON=$(PYTHON)

event-alpha-runs-report:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-runs-report --event-alpha-profile $(PROFILE)

.PHONY: event-impact-hypotheses-report event-incidents-report event-impact-hypotheses-inbox event-impact-hypothesis-smoke
event-impact-hypotheses-report:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	RSI_EVENT_IMPACT_HYPOTHESIS_STORE_PATH=$(EVENT_IMPACT_HYPOTHESIS_STORE_PATH) \
	$(PYTHON) main.py --event-impact-hypotheses-report --event-alpha-profile $(PROFILE) \
		$(if $(filter 1 true yes,$(LATEST)),--latest-run,) \
		$(if $(filter 1 true yes,$(ALL_HISTORY)),--all-history,) \
		$(if $(strip $(RUN_ID)),--run-id $(RUN_ID),) \
		$(if $(strip $(SINCE)),--since $(SINCE),) \
		$(if $(filter 1 true yes,$(INCLUDE_LEGACY)),--include-legacy,)

event-incidents-report:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-incidents-report --event-alpha-profile $(PROFILE) \
		$(if $(filter 1 true yes,$(LATEST)),--latest-run,) \
		$(if $(filter 1 true yes,$(ALL_HISTORY)),--all-history,) \
		$(if $(strip $(RUN_ID)),--run-id $(RUN_ID),) \
		$(if $(filter 1 true yes,$(INCLUDE_LEGACY)),--include-legacy,)

event-impact-hypotheses-inbox:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	RSI_EVENT_IMPACT_HYPOTHESIS_STORE_PATH=$(EVENT_IMPACT_HYPOTHESIS_STORE_PATH) \
	$(PYTHON) main.py --event-impact-hypotheses-inbox --event-alpha-profile $(PROFILE)

event-impact-hypothesis-smoke:
	$(EVENT_FIXTURE_NOW_ENV) $(PYTHON) main.py --event-impact-hypothesis-smoke

event-alpha-status:
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	RSI_EVENT_ALPHA_MISSED_PATH=$(EVENT_ALPHA_MISSED_PATH) \
	RSI_EVENT_IMPACT_HYPOTHESIS_STORE_PATH=$(EVENT_IMPACT_HYPOTHESIS_STORE_PATH) \
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-status --event-alpha-profile $(PROFILE)

event-alpha-preflight:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-preflight --event-alpha-profile $(PROFILE)

event-alpha-daily-report: PROFILE = no_key_live
event-alpha-daily-report:
	env $(EVENT_RESEARCH_NOW_ENV) \
	RSI_EVENT_WATCHLIST_MONITOR_ENABLED=1 \
	RSI_EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES=1 \
	$(PYTHON) main.py --event-alpha-status --event-alpha-profile no_key_live
	env $(EVENT_RESEARCH_NOW_ENV) \
	RSI_EVENT_WATCHLIST_MONITOR_ENABLED=1 \
	RSI_EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES=1 \
	$(PYTHON) main.py --event-alpha-cycle --event-alpha-profile no_key_live
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	$(PYTHON) main.py --event-alpha-runs-report --event-alpha-run-limit 5
	RSI_EVENT_ALPHA_ROUTER_ENABLED=1 \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	$(PYTHON) main.py --event-alpha-router-report
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	$(PYTHON) main.py --event-alpha-alerts-report

event-alpha-daily-llm-report: PROFILE = full_llm_live
event-alpha-daily-llm-report:
	env $(EVENT_RESEARCH_NOW_ENV) \
	RSI_EVENT_WATCHLIST_MONITOR_ENABLED=1 \
	RSI_EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES=1 \
	$(PYTHON) main.py --event-alpha-status --event-alpha-profile full_llm_live
	env $(EVENT_RESEARCH_NOW_ENV) \
	RSI_EVENT_WATCHLIST_MONITOR_ENABLED=1 \
	RSI_EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES=1 \
	$(PYTHON) main.py --event-alpha-cycle --event-alpha-profile full_llm_live
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	$(PYTHON) main.py --event-alpha-runs-report --event-alpha-run-limit 5
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	$(PYTHON) main.py --event-alpha-alerts-report

event-alpha-daily-send:
	@if [ "$${RSI_EVENT_ALERTS_ENABLED:-0}" != "1" ]; then \
		echo "Refusing Event Alpha daily send: set RSI_EVENT_ALERTS_ENABLED=1 to opt in."; \
		exit 2; \
	fi
	env $(EVENT_RESEARCH_NOW_ENV) \
	RSI_EVENT_WATCHLIST_MONITOR_ENABLED=1 \
	RSI_EVENT_WATCHLIST_MONITOR_ROUTE_UPDATES=1 \
	$(PYTHON) main.py --event-alpha-cycle --event-alpha-profile research_send --event-alert-send

event-alpha-health:
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	RSI_EVENT_ALPHA_MISSED_PATH=$(EVENT_ALPHA_MISSED_PATH) \
	$(PYTHON) main.py --event-alpha-status --event-alpha-profile $(PROFILE)
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	$(PYTHON) main.py --event-alpha-runs-report --event-alpha-run-limit 5

event-alpha-open-items:
	env $(EVENT_RESEARCH_NOW_ENV) \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	$(PYTHON) main.py --event-watchlist-monitor
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	RSI_EVENT_ALPHA_MISSED_PATH=$(EVENT_ALPHA_MISSED_PATH) \
	$(PYTHON) main.py --event-alpha-missed-report
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	RSI_EVENT_ALPHA_MISSED_PATH=$(EVENT_ALPHA_MISSED_PATH) \
	$(PYTHON) main.py --event-alpha-calibration-report

event-alpha-alerts-report:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-alerts-report --event-alpha-profile $(PROFILE)

event-alpha-fill-outcomes:
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	$(PYTHON) main.py --event-alpha-fill-outcomes $(EVENT_ALPHA_ALERT_PRICES) $(EVENT_ALPHA_ALERT_OUTCOMES)

event-watchlist-refresh:
	env $(EVENT_FIXTURE_NOW_ENV) \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_MARKET_ENRICHMENT_ENABLED=1 \
	RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 \
	RSI_EVENT_ANOMALY_MIN_RETURN_24H=$(EVENT_ALPHA_ANOMALY_MIN_RETURN_24H) \
	RSI_EVENT_ANOMALY_MIN_VOLUME_MCAP=$(EVENT_ALPHA_ANOMALY_MIN_VOLUME_MCAP) \
	RSI_EVENT_WATCHLIST_ENABLED=1 \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	$(PYTHON) main.py --event-watchlist-refresh

event-watchlist-report:
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	$(PYTHON) main.py --event-watchlist-report

event-watchlist-monitor:
	env $(EVENT_RESEARCH_NOW_ENV) \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	$(PYTHON) main.py --event-watchlist-monitor

event-alpha-router-report:
	RSI_EVENT_ALPHA_ROUTER_ENABLED=1 \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	$(PYTHON) main.py --event-alpha-router-report --event-alpha-profile $(PROFILE)

event-alpha-missed-report:
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-missed-report --event-alpha-profile $(PROFILE)

event-alpha-near-miss-report: PROFILE = notify_llm_quality
event-alpha-near-miss-report:
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-near-miss-report --event-alpha-profile $(PROFILE)

event-alpha-calibration-report:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-calibration-report --event-alpha-profile $(PROFILE)

event-source-reliability-report:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-source-reliability-report --event-alpha-profile $(PROFILE)

event-alpha-calibration-export-priors:
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_ALPHA_PRIORS_PATH=$(EVENT_ALPHA_PRIORS_OUT) \
	$(PYTHON) main.py --event-alpha-calibration-export-priors $(EVENT_ALPHA_PRIORS_OUT)

event-alpha-export-eval-cases:
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_ALPHA_MISSED_PATH=$(EVENT_ALPHA_MISSED_PATH) \
	RSI_EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR=$(EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR) \
	$(PYTHON) main.py --event-alpha-export-eval-cases-from-feedback $(EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR)
	RSI_EVENT_ALPHA_MISSED_PATH=$(EVENT_ALPHA_MISSED_PATH) \
	RSI_EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR=$(EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR) \
	$(PYTHON) main.py --event-alpha-export-eval-cases-from-missed $(EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR)

event-alpha-explain-last-run:
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	$(PYTHON) main.py --event-alpha-explain-last-run --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) $(EVENT_ALPHA_INCLUDE_LEGACY_ARG)

event-alpha-daily-brief:
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	RSI_EVENT_ALPHA_MISSED_PATH=$(EVENT_ALPHA_MISSED_PATH) \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	RSI_EVENT_RESEARCH_CARDS_DIR=$(EVENT_RESEARCH_CARDS_DIR) \
	RSI_EVENT_ALPHA_DAILY_BRIEF_PATH=$(EVENT_ALPHA_DAILY_BRIEF_PATH) \
	$(PYTHON) main.py --event-alpha-daily-brief --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) $(EVENT_ALPHA_INCLUDE_TEST_ARG) $(EVENT_ALPHA_INCLUDE_LEGACY_ARG)

event-alpha-replay:
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	$(PYTHON) main.py --event-alpha-replay --event-alpha-replay-priors --event-alpha-replay-llm-advisory

event-alpha-priors-shadow-report:
	env $(EVENT_RESEARCH_NOW_ENV) \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_MARKET_ENRICHMENT_ENABLED=1 \
	RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 \
	RSI_EVENT_ALPHA_PRIORS_PATH=$(EVENT_ALPHA_PRIORS_OUT) \
	$(PYTHON) main.py --event-alpha-priors-shadow-report

event-alpha-burn-in-no-key: PROFILE = no_key_live
event-alpha-burn-in-no-key:
	$(PYTHON) main.py --event-alpha-status --event-alpha-profile no_key_live
	env $(EVENT_RESEARCH_NOW_ENV) \
	$(PYTHON) main.py --event-alpha-cycle --event-alpha-profile no_key_live
	$(PYTHON) main.py --event-alpha-daily-brief --event-alpha-profile no_key_live
	$(PYTHON) main.py --event-alpha-explain-last-run --event-alpha-profile no_key_live

event-alpha-burn-in-llm: PROFILE = full_llm_live
event-alpha-burn-in-llm:
	$(PYTHON) main.py --event-alpha-status --event-alpha-profile full_llm_live
	env $(EVENT_RESEARCH_NOW_ENV) \
	$(PYTHON) main.py --event-alpha-cycle --event-alpha-profile full_llm_live
	$(PYTHON) main.py --event-alpha-daily-brief --event-alpha-profile full_llm_live
	$(PYTHON) main.py --event-alpha-explain-last-run --event-alpha-profile full_llm_live
	$(PYTHON) main.py --event-source-reliability-report --event-alpha-profile full_llm_live

event-alpha-weekly-review:
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	$(PYTHON) main.py --event-alpha-fill-outcomes $(EVENT_ALPHA_ALERT_PRICES) $(EVENT_ALPHA_ALERT_OUTCOMES)
	$(PYTHON) main.py --event-alpha-missed-report --event-alpha-profile $(PROFILE)
	$(PYTHON) main.py --event-alpha-calibration-report --event-alpha-profile $(PROFILE)
	$(PYTHON) main.py --event-source-reliability-report --event-alpha-profile $(PROFILE)
	$(MAKE) event-alpha-priors-shadow-report PYTHON=$(PYTHON)

event-alpha-burn-in-scorecard:
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	RSI_EVENT_ALPHA_MISSED_PATH=$(EVENT_ALPHA_MISSED_PATH) \
	RSI_EVENT_PROVIDER_HEALTH_PATH=$(EVENT_PROVIDER_HEALTH_PATH) \
	$(PYTHON) main.py --event-alpha-burn-in-scorecard --days 7 --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) $(EVENT_ALPHA_INCLUDE_LEGACY_ARG)

event-alpha-burn-in-checklist:
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	RSI_EVENT_ALPHA_MISSED_PATH=$(EVENT_ALPHA_MISSED_PATH) \
	RSI_EVENT_PROVIDER_HEALTH_PATH=$(EVENT_PROVIDER_HEALTH_PATH) \
	$(PYTHON) main.py --event-alpha-burn-in-checklist --days 7 --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) $(EVENT_ALPHA_INCLUDE_LEGACY_ARG)

event-alpha-v1-readiness:
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	RSI_EVENT_ALPHA_MISSED_PATH=$(EVENT_ALPHA_MISSED_PATH) \
	RSI_EVENT_PROVIDER_HEALTH_PATH=$(EVENT_PROVIDER_HEALTH_PATH) \
	$(PYTHON) main.py --event-alpha-v1-readiness --days 7 --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) $(EVENT_ALPHA_INCLUDE_LEGACY_ARG)

event-alpha-health-guard:
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	RSI_EVENT_PROVIDER_HEALTH_PATH=$(EVENT_PROVIDER_HEALTH_PATH) \
	RSI_EVENT_ALPHA_HEALTH_REQUIRE_PROFILE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-health-guard --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) $(EVENT_ALPHA_INCLUDE_LEGACY_ARG)

event-alpha-artifact-doctor:
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	RSI_EVENT_PROVIDER_HEALTH_PATH=$(EVENT_PROVIDER_HEALTH_PATH) \
	RSI_EVENT_ALPHA_FEEDBACK_PATH=$(EVENT_ALPHA_PROFILE_DIR)/event_alpha_feedback.jsonl \
	RSI_EVENT_RESEARCH_CARDS_DIR=$(EVENT_RESEARCH_CARDS_DIR) \
	$(PYTHON) main.py --event-alpha-artifact-doctor --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) $(EVENT_ALPHA_INCLUDE_TEST_ARG) $(EVENT_ALPHA_INCLUDE_LEGACY_ARG) $(EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT_ARG) $(EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT_LEGACY_ARG)

event-alpha-tuning-worksheet:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-alpha-tuning-worksheet --event-alpha-profile $(PROFILE)

event-alpha-export-burn-in-pack:
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	RSI_EVENT_ALPHA_MISSED_PATH=$(EVENT_ALPHA_MISSED_PATH) \
	RSI_EVENT_PROVIDER_HEALTH_PATH=$(EVENT_PROVIDER_HEALTH_PATH) \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	$(PYTHON) main.py --event-alpha-export-burn-in-pack $(EVENT_ALPHA_BURN_IN_PACK) --days 7 --event-alpha-profile $(PROFILE) --event-alpha-artifact-namespace $(PROFILE) $(EVENT_ALPHA_INCLUDE_LEGACY_ARG)

event-alpha-launchd-template:
	@echo "Launchd template: research/event_alpha_launchd_template.plist"
	@echo "Cron example:     research/event_alpha_cron_example.txt"

event-alpha-prune-artifacts:
	RSI_EVENT_ALPHA_RUN_LEDGER_PATH=$(EVENT_ALPHA_RUN_LEDGER_PATH) \
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_RESEARCH_CARDS_DIR=$(EVENT_RESEARCH_CARDS_DIR) \
	$(PYTHON) main.py --event-alpha-prune-artifacts $(if $(filter 1 true yes,$(CONFIRM)),--confirm,)

event-research-cards:
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	RSI_EVENT_ALPHA_ROUTER_ENABLED=1 \
	$(PYTHON) main.py --event-research-card $(ALERT_KEY)

event-research-cards-write:
	RSI_EVENT_ALPHA_ALERT_STORE_PATH=$(EVENT_ALPHA_ALERT_STORE_PATH) \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	RSI_EVENT_ALPHA_ROUTER_ENABLED=1 \
	RSI_EVENT_RESEARCH_CARDS_DIR=$(EVENT_RESEARCH_CARDS_DIR) \
	$(PYTHON) main.py --event-research-cards-write --event-alpha-profile $(PROFILE)

event-feedback-report:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-feedback-report --event-alpha-profile $(PROFILE)

event-feedback-useful:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-feedback-useful "$(FEEDBACK_TARGET)" --event-feedback-notes "$(FEEDBACK_NOTES)" --event-alpha-profile $(PROFILE)

event-feedback-junk:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-feedback-junk "$(FEEDBACK_TARGET)" --event-feedback-notes "$(FEEDBACK_NOTES)" --event-alpha-profile $(PROFILE)

event-feedback-watch:
	RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR=$(EVENT_ALPHA_ARTIFACT_BASE_DIR) \
	RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=$(PROFILE) \
	$(PYTHON) main.py --event-feedback-watch "$(FEEDBACK_TARGET)" --event-feedback-notes "$(FEEDBACK_NOTES)" --event-alpha-profile $(PROFILE)

event-alert-no-key-report:
	RSI_EVENT_DISCOVERY_LOOKBACK_HOURS=$(EVENT_DISCOVERY_RSS_LOOKBACK_HOURS) \
	RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=1 \
	RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH=$(EVENT_DISCOVERY_RSS_URLS_PATH) \
	RSI_EVENT_DISCOVERY_GDELT_LIVE=1 \
	RSI_EVENT_DISCOVERY_GDELT_QUERY='$(EVENT_DISCOVERY_GDELT_QUERY)' \
	RSI_EVENT_DISCOVERY_GDELT_MAX_RECORDS=$(EVENT_DISCOVERY_GDELT_MAX_RECORDS) \
	RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE=1 \
	RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT=$(EVENT_DISCOVERY_POLYMARKET_LIMIT) \
	RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1 \
	RSI_EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT=$(EVENT_DISCOVERY_RSS_UNIVERSE_FETCH_LIMIT) \
	$(PYTHON) main.py --event-alert-report

event-alert-no-key-llm-report:
	RSI_EVENT_DISCOVERY_LOOKBACK_HOURS=$(EVENT_DISCOVERY_RSS_LOOKBACK_HOURS) \
	RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=1 \
	RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH=$(EVENT_DISCOVERY_RSS_URLS_PATH) \
	RSI_EVENT_DISCOVERY_GDELT_LIVE=1 \
	RSI_EVENT_DISCOVERY_GDELT_QUERY='$(EVENT_DISCOVERY_GDELT_QUERY)' \
	RSI_EVENT_DISCOVERY_GDELT_MAX_RECORDS=$(EVENT_DISCOVERY_GDELT_MAX_RECORDS) \
	RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE=1 \
	RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT=$(EVENT_DISCOVERY_POLYMARKET_LIMIT) \
	RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1 \
	RSI_EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT=$(EVENT_DISCOVERY_RSS_UNIVERSE_FETCH_LIMIT) \
	RSI_EVENT_LLM_MODE=$(EVENT_ALERT_LLM_MODE) \
	RSI_EVENT_LLM_PROVIDER=$(EVENT_ALERT_LLM_PROVIDER) \
	$(PYTHON) main.py --event-alert-report --with-llm

event-alert-no-key-send:
	RSI_EVENT_DISCOVERY_LOOKBACK_HOURS=$(EVENT_DISCOVERY_RSS_LOOKBACK_HOURS) \
	RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=1 \
	RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH=$(EVENT_DISCOVERY_RSS_URLS_PATH) \
	RSI_EVENT_DISCOVERY_GDELT_LIVE=1 \
	RSI_EVENT_DISCOVERY_GDELT_QUERY='$(EVENT_DISCOVERY_GDELT_QUERY)' \
	RSI_EVENT_DISCOVERY_GDELT_MAX_RECORDS=$(EVENT_DISCOVERY_GDELT_MAX_RECORDS) \
	RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE=1 \
	RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT=$(EVENT_DISCOVERY_POLYMARKET_LIMIT) \
	RSI_EVENT_DISCOVERY_UNIVERSE_LIVE=1 \
	RSI_EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT=$(EVENT_DISCOVERY_RSS_UNIVERSE_FETCH_LIMIT) \
	RSI_EVENT_LLM_MODE=$(EVENT_ALERT_LLM_MODE) \
	RSI_EVENT_LLM_PROVIDER=$(EVENT_ALERT_LLM_PROVIDER) \
	$(PYTHON) main.py --event-alert-report --event-alert-send --with-llm

event-fade-auto-report:
	env $(EVENT_FIXTURE_NOW_ENV) \
	RSI_EVENT_DISCOVERY_EVENTS_PATH=fixtures/event_discovery/raw_events.json \
	RSI_EVENT_DISCOVERY_ALIASES_PATH=fixtures/event_discovery/asset_aliases.json \
	RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH=fixtures/event_discovery/binance_announcements.json \
	RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH=fixtures/event_discovery/bybit_announcements.json \
	RSI_EVENT_DISCOVERY_COINMARKETCAL_PATH=fixtures/event_discovery/coinmarketcal_events.json \
	RSI_EVENT_DISCOVERY_TOKENOMIST_PATH=fixtures/event_discovery/tokenomist_unlocks.json \
	RSI_EVENT_DISCOVERY_CRYPTOPANIC_PATH=fixtures/event_discovery/cryptopanic_news.json \
	RSI_EVENT_DISCOVERY_GDELT_PATH=fixtures/event_discovery/gdelt_news.json \
	RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH=fixtures/event_discovery/project_blog_rss.json \
	RSI_EVENT_DISCOVERY_EXTERNAL_IPO_PATH=fixtures/event_discovery/external_ipo_events.json \
	RSI_EVENT_DISCOVERY_SPORTS_FIXTURES_PATH=fixtures/event_discovery/sports_fixtures.json \
	RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH=fixtures/event_discovery/prediction_market_events.json \
	RSI_EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH=fixtures/event_discovery/coinalyze_derivatives.json \
	RSI_EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH=fixtures/event_discovery/tokenomist_supply.json \
	RSI_EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH=fixtures/event_discovery/etherscan_supply.json \
	RSI_EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH=fixtures/event_discovery/arkham_supply.json \
	RSI_EVENT_DISCOVERY_DUNE_SUPPLY_PATH=fixtures/event_discovery/dune_supply.json \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=fixtures/coingecko_smoke/top_markets.json \
	RSI_EVENT_DISCOVERY_LOOKBACK_HOURS=120 \
	RSI_EVENT_DISCOVERY_HORIZON_DAYS=2 \
	$(PYTHON) main.py --event-fade-auto-report

event-fade-export-sample:
	env $(EVENT_FIXTURE_NOW_ENV) \
	RSI_EVENT_DISCOVERY_EVENTS_PATH=fixtures/event_discovery/raw_events.json \
	RSI_EVENT_DISCOVERY_ALIASES_PATH=fixtures/event_discovery/asset_aliases.json \
	RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH=fixtures/event_discovery/binance_announcements.json \
	RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH=fixtures/event_discovery/bybit_announcements.json \
	RSI_EVENT_DISCOVERY_COINMARKETCAL_PATH=fixtures/event_discovery/coinmarketcal_events.json \
	RSI_EVENT_DISCOVERY_TOKENOMIST_PATH=fixtures/event_discovery/tokenomist_unlocks.json \
	RSI_EVENT_DISCOVERY_CRYPTOPANIC_PATH=fixtures/event_discovery/cryptopanic_news.json \
	RSI_EVENT_DISCOVERY_GDELT_PATH=fixtures/event_discovery/gdelt_news.json \
	RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH=fixtures/event_discovery/project_blog_rss.json \
	RSI_EVENT_DISCOVERY_EXTERNAL_IPO_PATH=fixtures/event_discovery/external_ipo_events.json \
	RSI_EVENT_DISCOVERY_SPORTS_FIXTURES_PATH=fixtures/event_discovery/sports_fixtures.json \
	RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH=fixtures/event_discovery/prediction_market_events.json \
	RSI_EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH=fixtures/event_discovery/coinalyze_derivatives.json \
	RSI_EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH=fixtures/event_discovery/tokenomist_supply.json \
	RSI_EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH=fixtures/event_discovery/etherscan_supply.json \
	RSI_EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH=fixtures/event_discovery/arkham_supply.json \
	RSI_EVENT_DISCOVERY_DUNE_SUPPLY_PATH=fixtures/event_discovery/dune_supply.json \
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=fixtures/coingecko_smoke/top_markets.json \
	RSI_EVENT_DISCOVERY_LOOKBACK_HOURS=120 \
	RSI_EVENT_DISCOVERY_HORIZON_DAYS=2 \
	$(PYTHON) main.py --event-fade-export-sample $(EVENT_FADE_SAMPLE_OUT)

event-fade-export-cache-sample:
	RSI_EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) \
	$(PYTHON) main.py --event-fade-export-cache-sample $(EVENT_FADE_SAMPLE_OUT)

event-fade-review-sample:
	$(PYTHON) main.py --event-fade-review-sample $(EVENT_FADE_SAMPLE_IN)

event-fade-labeling-queue:
	$(PYTHON) main.py --event-fade-labeling-queue $(EVENT_FADE_SAMPLE_IN) --event-fade-queue-limit $(EVENT_FADE_QUEUE_LIMIT)

event-fade-review-packet:
	$(PYTHON) main.py --event-fade-review-packet $(EVENT_FADE_SAMPLE_IN) $(EVENT_FADE_REVIEW_PACKET_OUT) --event-fade-queue-limit $(EVENT_FADE_QUEUE_LIMIT)

event-fade-export-review-template:
	$(PYTHON) main.py --event-fade-export-review-template $(EVENT_FADE_SAMPLE_IN) $(EVENT_FADE_REVIEW_TEMPLATE_OUT) --event-fade-queue-limit $(EVENT_FADE_QUEUE_LIMIT)

event-fade-apply-review-template:
	$(PYTHON) main.py --event-fade-apply-review-template $(EVENT_FADE_SAMPLE_IN) $(EVENT_FADE_REVIEW_TEMPLATE) $(EVENT_FADE_SAMPLE_REVIEW_APPLIED)

event-fade-check-review-template:
	$(PYTHON) main.py --event-fade-check-review-template $(EVENT_FADE_SAMPLE_IN) $(EVENT_FADE_REVIEW_TEMPLATE)

event-fade-check-review-bundle:
	$(PYTHON) main.py --event-fade-check-review-template $(EVENT_FADE_REVIEW_BUNDLE_SAMPLE) $(EVENT_FADE_REVIEW_BUNDLE_TEMPLATE)

event-fade-apply-review-bundle:
	$(PYTHON) main.py --event-fade-apply-review-template $(EVENT_FADE_REVIEW_BUNDLE_SAMPLE) $(EVENT_FADE_REVIEW_BUNDLE_TEMPLATE) $(EVENT_FADE_REVIEW_BUNDLE_APPLIED)

event-fade-review-applied-bundle:
	$(PYTHON) main.py --event-fade-review-sample $(EVENT_FADE_REVIEW_BUNDLE_APPLIED)

event-fade-fill-review-bundle-outcomes:
	$(PYTHON) main.py --event-fade-fill-outcomes $(EVENT_FADE_REVIEW_BUNDLE_APPLIED) $(EVENT_FADE_REVIEW_BUNDLE_OUTCOME_PRICES) $(EVENT_FADE_REVIEW_BUNDLE_OUTCOMES)

event-fade-review-bundle:
	env $(EVENT_RESEARCH_NOW_ENV) \
	$(PYTHON) main.py --event-fade-review-bundle $(EVENT_FADE_SAMPLE_IN) $(EVENT_FADE_REVIEW_BUNDLE_DIR) --event-fade-queue-limit $(EVENT_FADE_QUEUE_LIMIT) $(if $(EVENT_FADE_REVIEW_BUNDLE_PRICES),--event-fade-review-bundle-prices $(EVENT_FADE_REVIEW_BUNDLE_PRICES),) $(if $(EVENT_FADE_REVIEW_BUNDLE_REVIEWED),--event-fade-review-bundle-reviewed $(EVENT_FADE_REVIEW_BUNDLE_REVIEWED),) $(if $(EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES),--event-fade-review-bundle-export-prices --event-fade-price-days $(EVENT_FADE_PRICE_DAYS) --event-fade-price-interval $(EVENT_FADE_PRICE_INTERVAL) $(EVENT_FADE_PRICE_FIXTURE_ARG),)

event-fade-cache-review-bundle:
	RSI_EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) \
	env $(EVENT_RESEARCH_NOW_ENV) \
	$(PYTHON) main.py --event-fade-cache-review-bundle $(EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR) --event-fade-queue-limit $(EVENT_FADE_QUEUE_LIMIT) $(if $(EVENT_FADE_REVIEW_BUNDLE_PRICES),--event-fade-review-bundle-prices $(EVENT_FADE_REVIEW_BUNDLE_PRICES),) $(if $(EVENT_FADE_REVIEW_BUNDLE_REVIEWED),--event-fade-review-bundle-reviewed $(EVENT_FADE_REVIEW_BUNDLE_REVIEWED),) $(if $(EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES),--event-fade-review-bundle-export-prices --event-fade-price-days $(EVENT_FADE_PRICE_DAYS) --event-fade-price-interval $(EVENT_FADE_PRICE_INTERVAL) $(EVENT_FADE_PRICE_FIXTURE_ARG),)

event-fade-review-cycle:
	$(MAKE) event-discovery-refresh EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR)
	$(MAKE) event-fade-cache-review-bundle EVENT_RESEARCH_NOW=$(EVENT_FIXTURE_NOW) EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=$(EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR) EVENT_FADE_QUEUE_LIMIT=$(EVENT_FADE_QUEUE_LIMIT) EVENT_FADE_REVIEW_BUNDLE_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_PRICES) EVENT_FADE_REVIEW_BUNDLE_REVIEWED=$(EVENT_FADE_REVIEW_BUNDLE_REVIEWED) EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES) EVENT_FADE_PRICE_DAYS=$(EVENT_FADE_PRICE_DAYS) EVENT_FADE_PRICE_INTERVAL=$(EVENT_FADE_PRICE_INTERVAL) EVENT_FADE_PRICE_FIXTURE_DIR=$(EVENT_FADE_PRICE_FIXTURE_DIR)

event-fade-configured-review-cycle:
	$(MAKE) event-discovery-refresh-configured EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR)
	$(MAKE) event-fade-cache-review-bundle EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=$(EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR) EVENT_FADE_QUEUE_LIMIT=$(EVENT_FADE_QUEUE_LIMIT) EVENT_FADE_REVIEW_BUNDLE_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_PRICES) EVENT_FADE_REVIEW_BUNDLE_REVIEWED=$(EVENT_FADE_REVIEW_BUNDLE_REVIEWED) EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES) EVENT_FADE_PRICE_DAYS=$(EVENT_FADE_PRICE_DAYS) EVENT_FADE_PRICE_INTERVAL=$(EVENT_FADE_PRICE_INTERVAL) EVENT_FADE_PRICE_FIXTURE_DIR=$(EVENT_FADE_PRICE_FIXTURE_DIR)

event-fade-public-rss-review-cycle:
	$(MAKE) event-discovery-refresh-public-rss EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) EVENT_DISCOVERY_RSS_URLS_PATH=$(EVENT_DISCOVERY_RSS_URLS_PATH) EVENT_DISCOVERY_RSS_UNIVERSE_LIVE=$(EVENT_DISCOVERY_RSS_UNIVERSE_LIVE) EVENT_DISCOVERY_RSS_UNIVERSE_FETCH_LIMIT=$(EVENT_DISCOVERY_RSS_UNIVERSE_FETCH_LIMIT) EVENT_DISCOVERY_RSS_LOOKBACK_HOURS=$(EVENT_DISCOVERY_RSS_LOOKBACK_HOURS)
	$(MAKE) event-fade-cache-review-bundle EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=$(EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR) EVENT_FADE_QUEUE_LIMIT=$(EVENT_FADE_QUEUE_LIMIT) EVENT_FADE_REVIEW_BUNDLE_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_PRICES) EVENT_FADE_REVIEW_BUNDLE_REVIEWED=$(EVENT_FADE_REVIEW_BUNDLE_REVIEWED) EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES) EVENT_FADE_PRICE_DAYS=$(EVENT_FADE_PRICE_DAYS) EVENT_FADE_PRICE_INTERVAL=$(EVENT_FADE_PRICE_INTERVAL) EVENT_FADE_PRICE_FIXTURE_DIR=$(EVENT_FADE_PRICE_FIXTURE_DIR)

event-fade-gdelt-review-cycle:
	$(MAKE) event-discovery-refresh-gdelt EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) EVENT_DISCOVERY_GDELT_QUERY='$(EVENT_DISCOVERY_GDELT_QUERY)' EVENT_DISCOVERY_GDELT_MAX_RECORDS=$(EVENT_DISCOVERY_GDELT_MAX_RECORDS) EVENT_DISCOVERY_GDELT_UNIVERSE_LIVE=$(EVENT_DISCOVERY_GDELT_UNIVERSE_LIVE) EVENT_DISCOVERY_GDELT_UNIVERSE_FETCH_LIMIT=$(EVENT_DISCOVERY_GDELT_UNIVERSE_FETCH_LIMIT) EVENT_DISCOVERY_GDELT_LOOKBACK_HOURS=$(EVENT_DISCOVERY_GDELT_LOOKBACK_HOURS)
	$(MAKE) event-fade-cache-review-bundle EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=$(EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR) EVENT_FADE_QUEUE_LIMIT=$(EVENT_FADE_QUEUE_LIMIT) EVENT_FADE_REVIEW_BUNDLE_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_PRICES) EVENT_FADE_REVIEW_BUNDLE_REVIEWED=$(EVENT_FADE_REVIEW_BUNDLE_REVIEWED) EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES) EVENT_FADE_PRICE_DAYS=$(EVENT_FADE_PRICE_DAYS) EVENT_FADE_PRICE_INTERVAL=$(EVENT_FADE_PRICE_INTERVAL) EVENT_FADE_PRICE_FIXTURE_DIR=$(EVENT_FADE_PRICE_FIXTURE_DIR)

event-fade-polymarket-review-cycle:
	$(MAKE) event-discovery-refresh-polymarket EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) EVENT_DISCOVERY_POLYMARKET_LIMIT=$(EVENT_DISCOVERY_POLYMARKET_LIMIT) EVENT_DISCOVERY_POLYMARKET_UNIVERSE_LIVE=$(EVENT_DISCOVERY_POLYMARKET_UNIVERSE_LIVE) EVENT_DISCOVERY_POLYMARKET_UNIVERSE_FETCH_LIMIT=$(EVENT_DISCOVERY_POLYMARKET_UNIVERSE_FETCH_LIMIT)
	$(MAKE) event-fade-cache-review-bundle EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=$(EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR) EVENT_FADE_QUEUE_LIMIT=$(EVENT_FADE_QUEUE_LIMIT) EVENT_FADE_REVIEW_BUNDLE_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_PRICES) EVENT_FADE_REVIEW_BUNDLE_REVIEWED=$(EVENT_FADE_REVIEW_BUNDLE_REVIEWED) EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES) EVENT_FADE_PRICE_DAYS=$(EVENT_FADE_PRICE_DAYS) EVENT_FADE_PRICE_INTERVAL=$(EVENT_FADE_PRICE_INTERVAL) EVENT_FADE_PRICE_FIXTURE_DIR=$(EVENT_FADE_PRICE_FIXTURE_DIR)

event-fade-no-key-review-cycle:
	$(MAKE) event-discovery-refresh-public-rss EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) EVENT_DISCOVERY_RSS_URLS_PATH=$(EVENT_DISCOVERY_RSS_URLS_PATH) EVENT_DISCOVERY_RSS_UNIVERSE_LIVE=$(EVENT_DISCOVERY_RSS_UNIVERSE_LIVE) EVENT_DISCOVERY_RSS_UNIVERSE_FETCH_LIMIT=$(EVENT_DISCOVERY_RSS_UNIVERSE_FETCH_LIMIT) EVENT_DISCOVERY_RSS_LOOKBACK_HOURS=$(EVENT_DISCOVERY_RSS_LOOKBACK_HOURS)
	$(MAKE) event-discovery-refresh-gdelt EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) EVENT_DISCOVERY_GDELT_QUERY='$(EVENT_DISCOVERY_GDELT_QUERY)' EVENT_DISCOVERY_GDELT_MAX_RECORDS=$(EVENT_DISCOVERY_GDELT_MAX_RECORDS) EVENT_DISCOVERY_GDELT_UNIVERSE_LIVE=$(EVENT_DISCOVERY_GDELT_UNIVERSE_LIVE) EVENT_DISCOVERY_GDELT_UNIVERSE_FETCH_LIMIT=$(EVENT_DISCOVERY_GDELT_UNIVERSE_FETCH_LIMIT) EVENT_DISCOVERY_GDELT_LOOKBACK_HOURS=$(EVENT_DISCOVERY_GDELT_LOOKBACK_HOURS)
	$(MAKE) event-discovery-refresh-polymarket EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) EVENT_DISCOVERY_POLYMARKET_LIMIT=$(EVENT_DISCOVERY_POLYMARKET_LIMIT) EVENT_DISCOVERY_POLYMARKET_UNIVERSE_LIVE=$(EVENT_DISCOVERY_POLYMARKET_UNIVERSE_LIVE) EVENT_DISCOVERY_POLYMARKET_UNIVERSE_FETCH_LIMIT=$(EVENT_DISCOVERY_POLYMARKET_UNIVERSE_FETCH_LIMIT)
	$(MAKE) event-fade-cache-review-bundle EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=$(EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR) EVENT_FADE_QUEUE_LIMIT=$(EVENT_FADE_QUEUE_LIMIT) EVENT_FADE_REVIEW_BUNDLE_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_PRICES) EVENT_FADE_REVIEW_BUNDLE_REVIEWED=$(EVENT_FADE_REVIEW_BUNDLE_REVIEWED) EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES) EVENT_FADE_PRICE_DAYS=$(EVENT_FADE_PRICE_DAYS) EVENT_FADE_PRICE_INTERVAL=$(EVENT_FADE_PRICE_INTERVAL) EVENT_FADE_PRICE_FIXTURE_DIR=$(EVENT_FADE_PRICE_FIXTURE_DIR)

event-fade-merge-sample:
	$(PYTHON) main.py --event-fade-merge-sample $(EVENT_FADE_SAMPLE_FRESH) $(EVENT_FADE_SAMPLE_REVIEWED) $(EVENT_FADE_SAMPLE_MERGED)

event-fade-export-outcome-prices:
	$(PYTHON) main.py --event-fade-export-outcome-prices $(EVENT_FADE_SAMPLE_IN) $(EVENT_FADE_OUTCOME_PRICES_OUT) --event-fade-price-days $(EVENT_FADE_PRICE_DAYS) --event-fade-price-interval $(EVENT_FADE_PRICE_INTERVAL) $(EVENT_FADE_PRICE_FIXTURE_ARG)

event-fade-fill-outcomes:
	$(PYTHON) main.py --event-fade-fill-outcomes $(EVENT_FADE_SAMPLE_IN) $(EVENT_FADE_OUTCOME_PRICES) $(EVENT_FADE_SAMPLE_OUTCOMES)

status:
	$(PYTHON) main.py --status

backup-db:
	$(PYTHON) main.py --backup-db

verify-restore:
	$(PYTHON) main.py --verify-restore

maintenance:
	$(PYTHON) main.py --maintenance

rotate-logs:
	$(PYTHON) main.py --rotate-logs

launchd-status:
	$(PYTHON) main.py --launchd-status

install-maintenance-agent:
	$(PYTHON) main.py --install-maintenance-agent

restart-listener:
	$(PYTHON) main.py --restart-listener

universe-audit:
	$(PYTHON) main.py --universe-audit

refresh-universe-audit:
	$(PYTHON) main.py --refresh-universe-audit

dry-run:
	$(PYTHON) main.py --dry-run --top-n 30

dry-run-fixture:
	RSI_FIXTURE_DIR=fixtures/coingecko_smoke $(PYTHON) main.py --dry-run --top-n 3
