PYTHON := .venv/bin/python
EVENT_FADE_SAMPLE_OUT ?= /tmp/event_fade_validation_sample.jsonl
EVENT_FADE_SAMPLE_IN ?= $(EVENT_FADE_SAMPLE_OUT)

.PHONY: help verify test smoke-alerts backtest-fixture backtest-costs score score-json score-cohorts report event-fade-report event-discovery-report event-fade-auto-report event-fade-export-sample event-fade-review-sample status backup-db verify-restore maintenance rotate-logs launchd-status install-maintenance-agent restart-listener universe-audit refresh-universe-audit dry-run dry-run-fixture

help:
	@echo "Targets:"
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
	@echo "  make event-fade-auto-report  Print grouped event-fade discovery report"
	@echo "  make event-fade-export-sample  Write validation sample from fixtures"
	@echo "  make event-fade-review-sample  Review labels/outcomes in validation sample"
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

verify: test smoke-alerts backtest-fixture score

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

event-fade-auto-report:
	RSI_EVENT_DISCOVERY_EVENTS_PATH=fixtures/event_discovery/raw_events.json \
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

event-fade-review-sample:
	$(PYTHON) main.py --event-fade-review-sample $(EVENT_FADE_SAMPLE_IN)

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
