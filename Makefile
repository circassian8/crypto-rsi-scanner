PYTHON := .venv/bin/python

.PHONY: help verify test smoke-alerts score report dry-run

help:
	@echo "Targets:"
	@echo "  make verify   Run the standard local verification suite"
	@echo "  make test     Run standalone tests"
	@echo "  make smoke-alerts  Render representative alerts without sending"
	@echo "  make score    Print paper-trade scoreboard"
	@echo "  make report   Print signal outcome report"
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

dry-run:
	$(PYTHON) main.py --dry-run --top-n 30
