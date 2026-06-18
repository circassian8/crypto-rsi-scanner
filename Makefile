PYTHON ?= .venv/bin/python
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
EVENT_WATCHLIST_STATE_PATH ?= $(EVENT_DISCOVERY_CACHE_DIR)/event_watchlist_state.jsonl

.PHONY: help check-python bootstrap export-src verify test smoke-alerts backtest-fixture backtest-costs score score-json score-cohorts report event-fade-report event-discovery-report event-discovery-status event-discovery-runs event-discovery-refresh event-discovery-refresh-configured event-discovery-refresh-public-rss event-discovery-refresh-gdelt event-discovery-refresh-polymarket event-discovery-binance-listen event-llm-eval event-llm-extract-eval event-alpha-no-key-report event-watchlist-refresh event-watchlist-report event-alpha-router-report event-alert-no-key-report event-alert-no-key-llm-report event-alert-no-key-send event-fade-auto-report event-fade-export-sample event-fade-export-cache-sample event-fade-review-sample event-fade-labeling-queue event-fade-review-packet event-fade-export-review-template event-fade-apply-review-template event-fade-check-review-template event-fade-check-review-bundle event-fade-apply-review-bundle event-fade-review-applied-bundle event-fade-fill-review-bundle-outcomes event-fade-review-bundle event-fade-cache-review-bundle event-fade-review-cycle event-fade-configured-review-cycle event-fade-public-rss-review-cycle event-fade-gdelt-review-cycle event-fade-polymarket-review-cycle event-fade-no-key-review-cycle event-fade-merge-sample event-fade-export-outcome-prices event-fade-fill-outcomes status backup-db verify-restore maintenance rotate-logs launchd-status install-maintenance-agent restart-listener universe-audit refresh-universe-audit dry-run dry-run-fixture

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
	@echo "  make event-alpha-no-key-report  Print fixture market-anomaly event alpha radar"
	@echo "  make event-watchlist-refresh  Refresh fixture event-alpha watchlist state"
	@echo "  make event-watchlist-report  Print latest event-alpha watchlist state"
	@echo "  make event-alpha-router-report  Route latest watchlist state for research output"
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
	$(PYTHON) main.py --event-fade-report

event-discovery-report:
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

event-alpha-no-key-report:
	RSI_EVENT_DISCOVERY_UNIVERSE_PATH=$(EVENT_ALPHA_UNIVERSE_PATH) \
	RSI_EVENT_MARKET_ENRICHMENT_ENABLED=1 \
	RSI_EVENT_ANOMALY_SCANNER_ENABLED=1 \
	RSI_EVENT_ANOMALY_MIN_RETURN_24H=$(EVENT_ALPHA_ANOMALY_MIN_RETURN_24H) \
	RSI_EVENT_ANOMALY_MIN_VOLUME_MCAP=$(EVENT_ALPHA_ANOMALY_MIN_VOLUME_MCAP) \
	$(PYTHON) main.py --event-alpha-radar-report

event-watchlist-refresh:
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

event-alpha-router-report:
	RSI_EVENT_ALPHA_ROUTER_ENABLED=1 \
	RSI_EVENT_WATCHLIST_STATE_PATH=$(EVENT_WATCHLIST_STATE_PATH) \
	$(PYTHON) main.py --event-alpha-router-report

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
	$(PYTHON) main.py --event-fade-review-bundle $(EVENT_FADE_SAMPLE_IN) $(EVENT_FADE_REVIEW_BUNDLE_DIR) --event-fade-queue-limit $(EVENT_FADE_QUEUE_LIMIT) $(if $(EVENT_FADE_REVIEW_BUNDLE_PRICES),--event-fade-review-bundle-prices $(EVENT_FADE_REVIEW_BUNDLE_PRICES),) $(if $(EVENT_FADE_REVIEW_BUNDLE_REVIEWED),--event-fade-review-bundle-reviewed $(EVENT_FADE_REVIEW_BUNDLE_REVIEWED),) $(if $(EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES),--event-fade-review-bundle-export-prices --event-fade-price-days $(EVENT_FADE_PRICE_DAYS) --event-fade-price-interval $(EVENT_FADE_PRICE_INTERVAL) $(EVENT_FADE_PRICE_FIXTURE_ARG),)

event-fade-cache-review-bundle:
	RSI_EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) \
	$(PYTHON) main.py --event-fade-cache-review-bundle $(EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR) --event-fade-queue-limit $(EVENT_FADE_QUEUE_LIMIT) $(if $(EVENT_FADE_REVIEW_BUNDLE_PRICES),--event-fade-review-bundle-prices $(EVENT_FADE_REVIEW_BUNDLE_PRICES),) $(if $(EVENT_FADE_REVIEW_BUNDLE_REVIEWED),--event-fade-review-bundle-reviewed $(EVENT_FADE_REVIEW_BUNDLE_REVIEWED),) $(if $(EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES),--event-fade-review-bundle-export-prices --event-fade-price-days $(EVENT_FADE_PRICE_DAYS) --event-fade-price-interval $(EVENT_FADE_PRICE_INTERVAL) $(EVENT_FADE_PRICE_FIXTURE_ARG),)

event-fade-review-cycle:
	$(MAKE) event-discovery-refresh EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR)
	$(MAKE) event-fade-cache-review-bundle EVENT_DISCOVERY_CACHE_DIR=$(EVENT_DISCOVERY_CACHE_DIR) EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR=$(EVENT_FADE_CACHE_REVIEW_BUNDLE_DIR) EVENT_FADE_QUEUE_LIMIT=$(EVENT_FADE_QUEUE_LIMIT) EVENT_FADE_REVIEW_BUNDLE_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_PRICES) EVENT_FADE_REVIEW_BUNDLE_REVIEWED=$(EVENT_FADE_REVIEW_BUNDLE_REVIEWED) EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES=$(EVENT_FADE_REVIEW_BUNDLE_EXPORT_PRICES) EVENT_FADE_PRICE_DAYS=$(EVENT_FADE_PRICE_DAYS) EVENT_FADE_PRICE_INTERVAL=$(EVENT_FADE_PRICE_INTERVAL) EVENT_FADE_PRICE_FIXTURE_DIR=$(EVENT_FADE_PRICE_FIXTURE_DIR)

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
