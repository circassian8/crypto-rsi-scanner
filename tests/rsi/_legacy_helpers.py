"""Shared legacy helpers for RSI/CLI tests split from tests.test_indicators.

This intentionally mirrors the umbrella runner's common globals so mechanically
moved tests keep their original assertions and fixture behavior.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_TEST_INDICATORS_PATH = REPO_ROOT / "tests" / "test_indicators.py"
sys.path.insert(0, str(REPO_ROOT))

from crypto_rsi_scanner.indicators import (  # noqa: E402
    adaptive_thresholds,
    annualized_vol,
    btc_correlation,
    conviction_score,
    decide_flag,
    detect_divergence,
    regime_note,
    rsi_rate_of_change,
    rsi_z_score,
    trend_regime,
    volume_ratio,
    wilder_rsi,
)
from crypto_rsi_scanner.scanner import classify_tier  # noqa: E402
from crypto_rsi_scanner import formatting
import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status


def _market(**over):
    base = {
        "id": "bitcoin", "symbol": "btc", "name": "Bitcoin",
        "current_price": 100.0, "market_cap": 1_000_000_000.0,
        "total_volume": 20_000_000.0,
        "price_change_percentage_24h_in_currency": 2.0,
    }
    base.update(over)
    return base


def _sample_signal(**over):
    base = {
        "symbol": "BNB", "flag": "OB", "severity": "WATCH", "conviction": 50,
        "tier": "DIGEST", "is_new": True, "rsi_daily": 72.7, "rsi_4h": 74.3,
        "rsi_weekly": 50.2, "rsi_z": 2.4, "rsi_delta": 20.0, "volume_ratio": 7.0,
        "btc_corr": 0.4, "divergence": None, "regime": "DOWNTREND",
        "regime_note": "reversal?", "line": "  BNB . c50 ...",
    }
    base.update(over)
    return base


def _fresh_storage():
    import tempfile
    from crypto_rsi_scanner.storage import Storage
    return Storage(Path(tempfile.mkdtemp()) / "test.db")
