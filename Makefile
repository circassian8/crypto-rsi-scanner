PYTHON := .venv/bin/python

.PHONY: help verify test smoke-alerts score report status backup-db rotate-logs launchd-status restart-listener dry-run

help:
	@echo "Targets:"
	@echo "  make verify   Run the standard local verification suite"
	@echo "  make test     Run standalone tests"
	@echo "  make smoke-alerts  Render representative alerts without sending"
	@echo "  make score    Print paper-trade scoreboard"
	@echo "  make report   Print signal outcome report"
	@echo "  make status   Print operational scan/listener health"
	@echo "  make backup-db  Create and verify a SQLite backup"
	@echo "  make rotate-logs  Rotate oversized scan/listener logs"
	@echo "  make launchd-status  Print scan/listener launchd status"
	@echo "  make restart-listener  Restart the always-on bot listener"
	@echo "  make dry-run  Run a small network dry scan without writes/alerts"

verify: test smoke-alerts score

test:
	$(PYTHON) tests/test_indicators.py

smoke-alerts:
	$(PYTHON) -m crypto_rsi_scanner.alert_smoke

score:
	$(PYTHON) main.py --score

report:
	$(PYTHON) main.py --report

status:
	$(PYTHON) main.py --status

backup-db:
	$(PYTHON) main.py --backup-db

rotate-logs:
	$(PYTHON) main.py --rotate-logs

launchd-status:
	$(PYTHON) main.py --launchd-status

restart-listener:
	$(PYTHON) main.py --restart-listener

dry-run:
	$(PYTHON) main.py --dry-run --top-n 30
