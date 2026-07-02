"""Backtest CLI command group marker.

Backtest execution remains in ``python -m crypto_rsi_scanner.backtest``; the
scanner parser does not own a backtest flag. This module exists so command
inventory and classification have a stable group target.
"""

from __future__ import annotations

BACKTEST_COMMAND_GROUP = "backtest"


def handle(args) -> bool:
    return False
