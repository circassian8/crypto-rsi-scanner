"""Unit tests for the indicator math. Pure functions, no network.

Run with pytest:   pytest
Or standalone:     python tests/test_indicators.py
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_rsi_scanner.indicators import (
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
from crypto_rsi_scanner.scanner import classify_tier
from crypto_rsi_scanner import event_provider_status, formatting


def test_rsi_bounds():
    s = pd.Series(np.random.RandomState(0).randn(200).cumsum() + 100)
    rsi = wilder_rsi(s, 14).dropna()
    assert rsi.between(0, 100).all()


def test_rsi_pure_uptrend_is_high():
    s = pd.Series(np.arange(1, 101, dtype=float))  # strictly increasing
    rsi = wilder_rsi(s, 14).dropna()
    assert rsi.iloc[-1] == 100.0


def test_rsi_pure_downtrend_is_low():
    s = pd.Series(np.arange(100, 0, -1, dtype=float))  # strictly decreasing
    rsi = wilder_rsi(s, 14).dropna()
    assert rsi.iloc[-1] == 0.0


def test_rsi_matches_known_value():
    # Classic Wilder worked example (first 14 deltas), final RSI ~ 70.46
    closes = pd.Series([
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
        45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28,
    ])
    rsi = wilder_rsi(closes, 14).dropna()
    assert abs(rsi.iloc[-1] - 70.46) < 0.5


def test_annualized_vol_constant_is_zero():
    s = pd.Series([100.0] * 50)
    assert annualized_vol(s) == 0.0


def test_z_score_zero_when_flat():
    rsi = pd.Series([50.0] * 100)
    assert rsi_z_score(rsi, 90) == 0.0


def test_rate_of_change():
    rsi = pd.Series([50, 52, 55, 66], dtype=float)
    assert rsi_rate_of_change(rsi, 3) == 16.0


def test_adaptive_thresholds_ordering():
    rsi = pd.Series(np.linspace(20, 80, 100))
    ob, os_ = adaptive_thresholds(rsi, 95, 5)
    assert os_ < ob
    assert 20 <= os_ <= 80 and 20 <= ob <= 80


def test_adaptive_thresholds_fallback_when_short():
    rsi = pd.Series([50.0, 51.0])
    assert adaptive_thresholds(rsi) == (70.0, 30.0)


def test_volume_ratio_spike():
    vols = pd.Series([100.0] * 20 + [300.0])
    assert abs(volume_ratio(vols, 20) - 3.0) < 1e-6


def test_state_features_realized_vol_flat_and_changing():
    from crypto_rsi_scanner import state_features as sf

    flat = pd.Series([100.0] * 80)
    changing = pd.Series(np.linspace(100, 130, 80) + np.sin(np.arange(80)) * 3.0)
    assert sf.realized_vol(flat, window=20) == 0.0
    assert sf.realized_vol(changing, window=20) > 0.0
    vol_s = sf.realized_vol_series(changing, window=20)
    assert vol_s.dropna().iloc[-1] > 0.0


def test_state_features_trailing_percentile_is_trailing_only():
    from crypto_rsi_scanner import state_features as sf

    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 0.0])
    pct = sf.trailing_percentile_series(s, window=5)
    assert pct.iloc[4] >= 0.9      # current max in [1,2,3,4,5]
    assert pct.iloc[5] <= 0.1      # current min in [2,3,4,5,0]
    assert sf.trailing_percentile(pd.Series([10.0] * 10), window=5) == 0.5


def test_state_features_volatility_state_rules():
    from crypto_rsi_scanner import state_features as sf

    assert sf.volatility_state(float("nan"), 0.2, 0.5) == "unknown"
    assert sf.volatility_state(0.10, 0.20, 0.20) == "low_compressed"
    assert sf.volatility_state(0.25, 0.25, 0.50) == "normal"
    assert sf.volatility_state(0.35, 0.30, 0.72) == "high"
    assert sf.volatility_state(0.40, 0.30, 0.80) == "high_expanding"
    assert sf.volatility_state(0.50, 0.35, 0.95) == "crisis"


def test_makefile_has_clean_export_and_bootstrap_targets():
    import importlib.util
    import subprocess
    import time
    import zipfile
    from datetime import datetime
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    assert "PYTHON ?= .venv/bin/python" in makefile
    assert "EVENT_FIXTURE_NOW ?= 2026-06-15T16:00:00Z" in makefile
    assert "EVENT_RESEARCH_NOW ?=" in makefile
    assert "EVENT_FIXTURE_NOW_ENV = RSI_EVENT_RESEARCH_NOW=$(EVENT_FIXTURE_NOW)" in makefile
    assert "EVENT_RESEARCH_NOW_ENV = $(if $(strip $(EVENT_RESEARCH_NOW)),RSI_EVENT_RESEARCH_NOW=$(EVENT_RESEARCH_NOW),)" in makefile
    assert "event-incidents-report:" in makefile
    assert "--event-incidents-report" in makefile
    assert "RSI_EVENT_RESEARCH_NOW=$(EVENT_RESEARCH_NOW) \\" not in makefile
    notify_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-no-key", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_RESEARCH_NOW=" not in notify_dry
    notify_fixed_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-notify-no-key",
            "PYTHON=python3",
            "EVENT_RESEARCH_NOW=2026-06-20T12:00:00Z",
        ],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_RESEARCH_NOW=2026-06-20T12:00:00Z" in notify_fixed_dry
    notify_ignore_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-no-key", "PYTHON=python3", "IGNORE_BACKOFF=1"],
        cwd=root,
        text=True,
    )
    assert "--ignore-provider-backoff" in notify_ignore_dry
    day1_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-day1-start", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "event-alpha-preflight PROFILE=notify_no_key" in day1_dry
    assert "event-alpha-notification-checklist PROFILE=notify_no_key" in day1_dry
    assert "event-alpha-notify-preview PROFILE=notify_no_key" in day1_dry
    assert "main.py --event-alpha-send-test" not in day1_dry
    assert "main.py --event-alpha-notify-cycle" not in day1_dry
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=notify_no_key" in day1_dry
    fixture_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-cycle", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_RESEARCH_NOW=2026-06-15T16:00:00Z" in fixture_dry
    notify_report_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-notification-runs-report",
            "PROFILE=notify_no_key",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=notify_no_key" in notify_report_dry
    assert "--event-alpha-notification-runs-report --event-alpha-profile notify_no_key" in notify_report_dry
    assert "RSI_EVENT_ALPHA_NOTIFICATION_RUNS_PATH=" not in notify_report_dry
    inbox_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notification-inbox", "PROFILE=notify_no_key", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-notification-inbox --event-alpha-profile notify_no_key" in inbox_dry
    fixture_smoke_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-fixture-smoke", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-notify-fixture-smoke" in fixture_smoke_dry
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=fixture_notify_smoke" in fixture_smoke_dry
    deep_no_send_smoke_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-llm-deep-no-send-smoke", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-notify-fixture-smoke" in deep_no_send_smoke_dry
    assert "RSI_EVENT_ALPHA_NOTIFY_FIXTURE_NO_SEND=1" in deep_no_send_smoke_dry
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=notify_llm_deep_no_send_smoke" in deep_no_send_smoke_dry
    deep_research_review_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-llm-deep-research-review-no-send-smoke", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_ALPHA_NOTIFY_FIXTURE_PROFILE=notify_llm_deep" in deep_research_review_dry
    assert "RSI_EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED=1" in deep_research_review_dry
    assert "research_review_digest_candidates" in deep_research_review_dry
    assert "notify_llm_deep_research_review_smoke" in deep_research_review_dry
    assert "--event-alpha-source-coverage-report --event-alpha-profile notify_llm_deep --event-alpha-artifact-namespace notify_llm_deep_research_review_smoke" in deep_research_review_dry
    assert "event_alpha_source_coverage.md" in deep_research_review_dry
    assert "--event-alpha-daily-brief --event-alpha-profile notify_llm_deep --event-alpha-artifact-namespace notify_llm_deep_research_review_smoke --event-alpha-include-test-artifacts" in deep_research_review_dry
    assert "event_alpha_daily_brief.md" in deep_research_review_dry
    assert "--event-alpha-artifact-doctor-delivery-scope latest_run" in deep_research_review_dry
    daily_brief_namespace_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-daily-brief",
            "PROFILE=notify_llm_deep",
            "ARTIFACT_NAMESPACE=notify_llm_deep_research_review_smoke",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-profile notify_llm_deep --event-alpha-artifact-namespace notify_llm_deep_research_review_smoke --event-alpha-include-test-artifacts" in daily_brief_namespace_dry
    source_coverage_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-source-coverage-report",
            "PROFILE=notify_llm_deep",
            "ARTIFACT_NAMESPACE=notify_llm_deep_research_review_smoke",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=notify_llm_deep_research_review_smoke" in source_coverage_dry
    assert "--event-alpha-profile notify_llm_deep --event-alpha-artifact-namespace notify_llm_deep_research_review_smoke" in source_coverage_dry
    doctor_namespace_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-artifact-doctor",
            "PROFILE=notify_llm_deep_research_review_smoke",
            "STRICT=1",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-profile notify_llm_deep --event-alpha-artifact-namespace notify_llm_deep_research_review_smoke" in doctor_namespace_dry
    deep_rehearsal_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-llm-deep-real-no-send-rehearsal", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-notify-cycle --event-alpha-profile notify_llm_deep --event-alert-send" in deep_rehearsal_dry
    assert "RSI_EVENT_ALERTS_ENABLED=0" in deep_rehearsal_dry
    assert "RSI_EVENT_ALERTS_ENABLED=1" not in deep_rehearsal_dry
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=notify_llm_deep_rehearsal" in deep_rehearsal_dry
    assert "RSI_EVENT_RESEARCH_CARDS_WRITE_LIMIT=250" in deep_rehearsal_dry
    assert "--event-alpha-artifact-doctor-delivery-scope latest_run" in deep_rehearsal_dry
    cryptopanic_preflight_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-cryptopanic-preflight", "PROFILE=notify_llm_deep", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-cryptopanic-preflight --event-alpha-profile notify_llm_deep" in cryptopanic_preflight_dry
    cryptopanic_rehearsal_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-llm-deep-cryptopanic-no-send-rehearsal", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "notify_llm_deep_cryptopanic_rehearsal" in cryptopanic_rehearsal_dry
    assert "--event-alpha-cryptopanic-preflight --event-alpha-profile notify_llm_deep" in cryptopanic_rehearsal_dry
    assert "--event-alpha-notify-cycle --event-alpha-profile notify_llm_deep --event-alert-send" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_ALERTS_ENABLED=0" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_CATALYST_SEARCH_MAX_ANOMALIES=2" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_CANDIDATES=2" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_QUERIES=4" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_DISCOVERY_CRYPTOPANIC_TIMEOUT=3" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_RUN_LIMIT=8" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_DISCOVERY_CRYPTOPANIC_MAX_PAGES_PER_QUERY=1" in cryptopanic_rehearsal_dry
    assert "event-alpha-telegram-send-one-cycle" not in cryptopanic_rehearsal_dry
    coinalyze_preflight_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-coinalyze-preflight", "PROFILE=notify_llm_deep", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-coinalyze-preflight --event-alpha-profile notify_llm_deep" in coinalyze_preflight_dry
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=coinalyze_preflight" in coinalyze_preflight_dry
    assert "--event-alpha-artifact-namespace coinalyze_preflight" in coinalyze_preflight_dry
    assert "RSI_EVENT_ALERTS_ENABLED=0" in coinalyze_preflight_dry
    assert "--event-alpha-coinalyze-allow-live-preflight" not in coinalyze_preflight_dry
    coinalyze_smoke_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-coinalyze-preflight-smoke", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-coinalyze-preflight-smoke --event-alpha-profile fixture" in coinalyze_smoke_dry
    assert "RSI_EVENT_DISCOVERY_COINALYZE_API_KEY=" in coinalyze_smoke_dry
    assert "--event-alpha-coinalyze-allow-live-preflight" not in coinalyze_smoke_dry
    coinalyze_rehearsal_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-coinalyze-no-send-rehearsal", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=coinalyze_no_send_rehearsal" in coinalyze_rehearsal_dry
    assert "--event-alpha-artifact-namespace coinalyze_no_send_rehearsal" in coinalyze_rehearsal_dry
    assert "--event-alpha-coinalyze-allow-live-preflight" not in coinalyze_rehearsal_dry
    dex_onchain_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-dex-onchain-readiness-smoke", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-dex-onchain-readiness-smoke --event-alpha-profile fixture" in dex_onchain_dry
    assert "RSI_EVENT_ALPHA_DEX_GECKOTERMINAL_PATH=fixtures/event_dex_onchain/geckoterminal_pools.json" in dex_onchain_dry
    assert "RSI_EVENT_ALPHA_DEX_COINGECKO_PATH=fixtures/event_dex_onchain/coingecko_dex_pools.json" in dex_onchain_dry
    assert "RSI_EVENT_ALPHA_PROTOCOL_DEFILLAMA_PATH=fixtures/event_dex_onchain/defillama_protocol_fundamentals.json" in dex_onchain_dry
    assert "RSI_EVENT_ALERTS_ENABLED=0" in dex_onchain_dry
    bybit_preflight_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-bybit-announcements-preflight", "PROFILE=notify_llm_deep", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-bybit-announcements-preflight --event-alpha-profile notify_llm_deep" in bybit_preflight_dry
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=bybit_announcements_preflight" in bybit_preflight_dry
    assert "--event-alpha-artifact-namespace bybit_announcements_preflight" in bybit_preflight_dry
    assert "RSI_EVENT_ALERTS_ENABLED=0" in bybit_preflight_dry
    assert "--event-alpha-bybit-announcements-allow-live-preflight" not in bybit_preflight_dry
    bybit_smoke_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-bybit-announcements-preflight-smoke", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-bybit-announcements-preflight-smoke --event-alpha-profile fixture" in bybit_smoke_dry
    assert "RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH=fixtures/event_discovery/official_exchange_bybit_announcements.json" in bybit_smoke_dry
    assert "--event-alpha-bybit-announcements-allow-live-preflight" not in bybit_smoke_dry
    bybit_rehearsal_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-bybit-announcements-no-send-rehearsal", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=bybit_announcements_no_send_rehearsal" in bybit_rehearsal_dry
    assert "--event-alpha-artifact-namespace bybit_announcements_no_send_rehearsal" in bybit_rehearsal_dry
    assert "--event-alpha-bybit-announcements-allow-live-preflight" not in bybit_rehearsal_dry
    notify_preview_from_artifacts_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-notify-preview-from-artifacts",
            "PROFILE=notify_llm_deep",
            "ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-notify-preview-from-artifacts --event-alpha-profile notify_llm_deep" in notify_preview_from_artifacts_dry
    assert "RSI_EVENT_ALERTS_ENABLED=0" in notify_preview_from_artifacts_dry
    known_stale_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-mark-known-stale-namespaces", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-mark-known-stale-namespaces" in known_stale_dry
    assert "check-python:" in makefile
    assert "bootstrap:" in makefile
    assert "python3 -m venv .venv" in makefile
    assert "export-src:" in makefile
    assert "git archive --format=zip -o crypto-rsi-scanner-source.zip HEAD" in makefile
    assert "export-src-with-artifacts:" in makefile
    assert "python3 scripts/export_source_with_artifacts.py" in makefile
    assert "event-fade-check-review-template:" in makefile
    assert "--event-fade-check-review-template $(EVENT_FADE_SAMPLE_IN) $(EVENT_FADE_REVIEW_TEMPLATE)" in makefile
    assert "event-fade-check-review-bundle:" in makefile
    assert "--event-fade-check-review-template $(EVENT_FADE_REVIEW_BUNDLE_SAMPLE) $(EVENT_FADE_REVIEW_BUNDLE_TEMPLATE)" in makefile
    assert "event-fade-apply-review-bundle:" in makefile
    assert "--event-fade-apply-review-template $(EVENT_FADE_REVIEW_BUNDLE_SAMPLE) $(EVENT_FADE_REVIEW_BUNDLE_TEMPLATE) $(EVENT_FADE_REVIEW_BUNDLE_APPLIED)" in makefile
    assert "event-fade-review-applied-bundle:" in makefile
    assert "--event-fade-review-sample $(EVENT_FADE_REVIEW_BUNDLE_APPLIED)" in makefile
    assert "event-fade-fill-review-bundle-outcomes:" in makefile
    assert "--event-fade-fill-outcomes $(EVENT_FADE_REVIEW_BUNDLE_APPLIED) $(EVENT_FADE_REVIEW_BUNDLE_OUTCOME_PRICES) $(EVENT_FADE_REVIEW_BUNDLE_OUTCOMES)" in makefile
    assert "Run 'make bootstrap' or override with 'make verify PYTHON=python3'." in makefile

    export_dry = subprocess.run(
        ["make", "-n", "export-src"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "git archive --format=zip -o crypto-rsi-scanner-source.zip HEAD" in export_dry.stdout

    export_artifacts_dry = subprocess.run(
        ["make", "-n", "export-src-with-artifacts"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "python3 scripts/export_source_with_artifacts.py" in export_artifacts_dry.stdout

    spec = importlib.util.spec_from_file_location(
        "export_source_with_artifacts",
        root / "scripts" / "export_source_with_artifacts.py",
    )
    assert spec and spec.loader
    export_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export_module)
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        future_file = tmp_path / "Makefile"
        future_file.write_text("all:\n\t@true\n", encoding="utf-8")
        now_ts = time.time()
        future_ts = now_ts + 86400
        os.utime(future_file, (future_ts, future_ts))
        out_zip = tmp_path / "out.zip"
        with zipfile.ZipFile(out_zip, "w") as zf:
            export_module._write_file_to_zip(zf, future_file, "Makefile", now_ts=now_ts)
        with zipfile.ZipFile(out_zip) as zf:
            zipped_ts = datetime(*zf.getinfo("Makefile").date_time).timestamp()
        assert zipped_ts <= now_ts + 2
        assert zipped_ts < future_ts - 3600
        original_epoch = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = "315619200"
        try:
            safe_ts = export_module._safe_export_timestamp(now_ts=now_ts)
        finally:
            if original_epoch is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = original_epoch
        assert safe_ts == 315619200

    verify_dry = subprocess.run(
        ["make", "-n", "verify", "PYTHON=python3"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "python3 tests/test_indicators.py" in verify_dry.stdout
    assert ".venv/bin/python tests/test_indicators.py" not in verify_dry.stdout

    bundle_check_dry = subprocess.run(
        [
            "make",
            "-n",
            "event-fade-check-review-bundle",
            "PYTHON=python3",
            "EVENT_FADE_REVIEW_BUNDLE_DIR=/tmp/review_bundle",
        ],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert (
        "python3 main.py --event-fade-check-review-template "
        "/tmp/review_bundle/validation_sample.jsonl "
        "/tmp/review_bundle/review_template_balanced.csv"
    ) in bundle_check_dry.stdout

    bundle_outcomes_dry = subprocess.run(
        [
            "make",
            "-n",
            "event-fade-fill-review-bundle-outcomes",
            "PYTHON=python3",
            "EVENT_FADE_REVIEW_BUNDLE_DIR=/tmp/review_bundle",
        ],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert (
        "python3 main.py --event-fade-fill-outcomes "
        "/tmp/review_bundle/validation_sample_reviewed.jsonl "
        "/tmp/review_bundle/outcome_prices.json "
        "/tmp/review_bundle/validation_sample_reviewed_with_outcomes.jsonl"
    ) in bundle_outcomes_dry.stdout


def test_state_features_cross_sectional_ranks_monotonic():
    from crypto_rsi_scanner import state_features as sf

    ranks = sf.cross_sectional_ranks({"weak": -1.0, "mid": 0.0, "strong": 2.0})
    assert ranks["weak"] == 0.0
    assert ranks["mid"] == 0.5
    assert ranks["strong"] == 1.0
    tied = sf.cross_sectional_ranks({"a": 1.0, "b": 1.0, "c": float("nan")})
    assert tied["a"] == tied["b"]
    assert tied["c"] == 0.5


def test_state_features_rolling_beta_synthetic():
    from crypto_rsi_scanner import state_features as sf

    rng = np.random.RandomState(7)
    btc_ret = rng.normal(0.0005, 0.01, 140)
    asset_ret = 2.0 * btc_ret + rng.normal(0.0, 0.001, 140)
    eth_ret = rng.normal(0.0002, 0.012, 140)
    btc = pd.Series(100.0 * np.cumprod(1.0 + btc_ret))
    asset = pd.Series(50.0 * np.cumprod(1.0 + asset_ret))
    eth = pd.Series(80.0 * np.cumprod(1.0 + eth_ret))

    assert abs(sf.rolling_beta(asset, btc, window=120) - 2.0) < 0.15
    multi = sf.rolling_multi_beta(asset, {"BTC": btc, "ETH": eth}, window=120)
    assert abs(multi["beta_BTC"] - 2.0) < 0.15
    assert abs(multi["beta_ETH"]) < 0.15
    assert 0.0 <= multi["r2"] <= 1.0


def test_state_features_volume_and_liquidity():
    from crypto_rsi_scanner import state_features as sf

    volume = pd.Series([100.0] * 89 + [250.0])
    close = pd.Series([10.0] * 90)
    market_cap = pd.Series([10_000.0] * 90)

    assert sf.volume_z_score(volume, window=90) > 5.0
    assert sf.dollar_volume_20(close, volume, volume_is_usd=True) > 100.0
    assert sf.dollar_volume_20(close, volume, volume_is_usd=False) > 1000.0
    assert sf.turnover_20(close * volume, market_cap) > 0.10
    assert sf.volume_price_state(-0.04, 2.0) == "down_high_volume"
    assert sf.volume_price_state(0.04, 2.0) == "up_high_volume"
    assert sf.volume_price_state(0.0, 2.0) == "spike_flat_price"
    assert sf.volume_price_state(0.04, 0.0) == "up_normal_volume"
    assert sf.rank_bucket(0.9) == "high"
    assert sf.rank_bucket(0.1) == "low"
    assert sf.liquidity_bucket(1_000_000, 0.02) == "low"
    assert sf.liquidity_bucket(200_000_000, 0.0) == "high"
    assert sf.falling_knife_bucket(75) == "high"
    assert sf.falling_knife_score(
        vol_state="crisis",
        breadth_state="breadth_collapse",
        rs_bucket="low",
        regime="DOWNTREND",
        volume_state="down_high_volume",
        ret_30d=-0.30,
        btc_beta_60=1.5,
        beta_r2_60=0.6,
    ) >= 90


def test_state_features_breadth_snapshot_handles_missing_and_short_histories():
    from crypto_rsi_scanner import state_features as sf

    assert sf.breadth_snapshot({"a": pd.Series([1.0, 2.0])}, {})["state"] == "unknown"

    idx = pd.date_range("2026-01-01", periods=220, freq="D", tz="UTC")
    closes = {
        "a": pd.Series(np.linspace(10, 40, 220), index=idx),
        "b": pd.Series(np.linspace(20, 50, 220), index=idx),
        "c": pd.Series(np.linspace(30, 45, 220), index=idx),
        "short": pd.Series([1.0, 2.0, 3.0], index=idx[:3]),
    }
    rsi = {
        "a": pd.Series([65.0] * 220, index=idx),
        "b": pd.Series([62.0] * 220, index=idx),
        "c": pd.Series([45.0] * 220, index=idx),
    }
    snap = sf.breadth_snapshot(closes, rsi, asof=idx[-1])
    assert snap["median_rsi"] == 62.0
    assert snap["pct_rsi_gt_60"] == 2 / 3
    assert snap["pct_above_50dma"] == 1.0
    assert snap["pct_above_200dma"] == 1.0
    assert snap["state"] == "risk_on_broad"


def test_btc_correlation_perfect():
    btc = pd.Series(np.arange(1, 41, dtype=float))
    coin = btc * 2.0  # perfectly correlated returns
    assert btc_correlation(coin, btc, 30) > 0.99


def test_divergence_bearish():
    # price higher high, RSI lower high -> bearish
    n = 40
    price = pd.Series(np.concatenate([
        np.linspace(10, 20, 10),  # peak ~20
        np.linspace(20, 12, 10),
        np.linspace(12, 25, 10),  # higher peak ~25
        np.linspace(25, 18, 10),
    ]))
    rsi = pd.Series(np.concatenate([
        np.linspace(40, 85, 10),  # high RSI peak
        np.linspace(85, 45, 10),
        np.linspace(45, 70, 10),  # lower RSI peak
        np.linspace(70, 55, 10),
    ]))
    assert detect_divergence(price, rsi, lookback=40, order=3) == "bearish"


# --- event-fade research sleeve ---------------------------------------------

def _event_provider_status_cfg(**overrides):
    values = {
        "EVENT_DISCOVERY_MODE": "research_only",
        "EVENT_DISCOVERY_CACHE_DIR": "/tmp/event_fade_cache",
        "EVENT_DISCOVERY_LOOKBACK_HOURS": 72,
        "EVENT_DISCOVERY_HORIZON_DAYS": 14,
        "EVENT_DISCOVERY_EVENTS_PATH": None,
        "EVENT_DISCOVERY_ALIASES_PATH": "fixtures/event_discovery/asset_aliases.json",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH": None,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE": False,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY": "",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET": "",
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH": None,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE": False,
        "EVENT_DISCOVERY_COINMARKETCAL_PATH": None,
        "EVENT_DISCOVERY_TOKENOMIST_PATH": None,
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH": None,
        "EVENT_DISCOVERY_CRYPTOPANIC_LIVE": False,
        "EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN": "",
        "EVENT_DISCOVERY_GDELT_PATH": None,
        "EVENT_DISCOVERY_GDELT_LIVE": False,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH": None,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": False,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS": (),
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH": None,
        "EVENT_DISCOVERY_EXTERNAL_IPO_PATH": None,
        "EVENT_DISCOVERY_SPORTS_FIXTURES_PATH": None,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH": None,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": False,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIMIT": 100,
        "EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH": None,
        "EVENT_DISCOVERY_COINALYZE_LIVE": False,
        "EVENT_DISCOVERY_COINALYZE_API_KEY": "",
        "EVENT_DISCOVERY_COINALYZE_SYMBOLS": (),
        "EVENT_DISCOVERY_COINALYZE_AUTO_SYMBOLS": True,
        "EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH": None,
        "EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH": None,
        "EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH": None,
        "EVENT_DISCOVERY_DUNE_SUPPLY_PATH": None,
        "EVENT_DISCOVERY_UNIVERSE_PATH": None,
        "EVENT_DISCOVERY_UNIVERSE_LIVE": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)
















def test_config_load_url_list_dedupes_comments_and_inline_notes():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "feeds.txt"
        path.write_text(
            "\n".join([
                "# public feeds",
                "https://example.test/rss",
                "https://example.test/rss  # duplicate",
                "",
                "https://example.test/atom",
            ]),
            encoding="utf-8",
        )

        urls = config._load_url_list(path)

    assert urls == ("https://example.test/rss", "https://example.test/atom")






















def _event_fade_velvet_candidate(now=None, *, direct=False, no_event_time=False, btc_risk_on=35):
    from datetime import datetime, timezone, timedelta
    from crypto_rsi_scanner import event_fade as ef

    now = now or datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    event_time = None if no_event_time else now - timedelta(hours=2)
    event = ef.CatalystEvent(
        event_id="testvelvet-spacex",
        coin_id="testvelvet",
        symbol="TESTVELVET",
        event_name="SpaceX IPO trading start",
        event_type="etf_approval" if direct else "ipo_proxy",
        event_time=event_time,
        first_seen_time=now - timedelta(days=2),
        source="manual_fixture",
        confidence=0.95,
        external_asset=None if direct else "SpaceX",
        is_proxy_narrative=not direct,
        is_direct_beneficiary=direct,
    )
    market = ef.EventMarketSnapshot(
        symbol="TESTVELVET",
        coin_id="testvelvet",
        timestamp=now,
        price=7.2,
        spot_volume_24h=8_000_000,
        market_cap=45_000_000,
        return_24h=1.2,
        return_72h=3.5,
        return_7d=8.5,
        distance_from_20d_ma=2.0,
        volume_zscore_24h=6.2,
        order_book_depth_1pct=8_000,
        order_book_depth_2pct=25_000,
        spread_bps=45,
    )
    derivatives = ef.EventDerivativesSnapshot(
        symbol="TESTVELVET",
        timestamp=now,
        perp_available=True,
        open_interest_24h_change_pct=0.65,
        open_interest_to_market_cap=0.40,
        funding_rate_8h=0.0012,
        perp_spot_volume_ratio=22,
        long_short_ratio=2.1,
        basis=0.025,
    )
    supply = ef.EventSupplyPressureSnapshot(
        symbol="TESTVELVET",
        timestamp=now,
        large_holder_exchange_inflow=True,
        cex_inflow_pct_supply=0.02,
        top_holder_concentration=0.62,
        team_or_mm_wallet_activity=True,
    )
    rsi = ef.EventRSISnapshot(
        symbol="TESTVELVET",
        timestamp=now,
        rsi_daily=86,
        rsi_4h=78,
        rsi_weekly=72,
        target_overbought_score=90,
        btc_risk_on_score=btc_risk_on,
        rsi_rollover_confirmed=True,
        bearish_rsi_divergence=True,
    )
    technical = ef.EventTechnicalSnapshot(
        symbol="TESTVELVET",
        timestamp=now,
        event_vwap=8.1,
        price_below_event_vwap=True,
        failed_reclaim_event_vwap=True,
        lower_high_confirmed=True,
        first_support_broken=True,
        post_event_high=9.4,
        post_event_lower_high=8.6,
        invalidation_level=8.65,
        entry_reference_price=7.2,
    )
    return ef.FadeCandidate(
        "TESTVELVET", "testvelvet", event, market, derivatives, supply, rsi, technical
    )






















# --- event discovery research sleeve ----------------------------------------

def _event_discovery_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "raw_events.json", root / "asset_aliases.json"


def _coingecko_universe_fixture_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "coingecko_smoke" / "top_markets.json"


def _exchange_announcement_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "binance_announcements.json", root / "bybit_announcements.json"


def _structured_calendar_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "coinmarketcal_events.json", root / "tokenomist_unlocks.json"


def _derivatives_fixture_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery" / "coinalyze_derivatives.json"


def _news_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "cryptopanic_news.json", root / "gdelt_news.json", root / "project_blog_rss.json"


def _external_catalyst_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return root / "external_ipo_events.json", root / "sports_fixtures.json", root / "prediction_market_events.json"


def _supply_fixture_paths():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery"
    return (
        root / "tokenomist_supply.json",
        root / "etherscan_supply.json",
        root / "arkham_supply.json",
        root / "dune_supply.json",
    )


def _outcome_prices_fixture_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery" / "outcome_prices.json"


def _outcome_klines_fixture_dir():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery" / "outcome_klines"


def _llm_golden_fixture_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery" / "llm_golden_cases.json"


def _llm_extraction_golden_fixture_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "fixtures" / "event_discovery" / "llm_extraction_golden_cases.json"


def _stamp_review_provenance(row, reviewer="human", reviewed_at="2026-06-17T12:00:00+00:00"):
    row["reviewed_by"] = reviewer
    row["reviewed_at"] = reviewed_at
    return row


def _test_normalized_event(
    title,
    body="",
    *,
    event_id="test-event",
    event_type="ipo_proxy",
    external_asset="SpaceX",
    event_time=None,
    event_time_confidence=0.0,
    confidence=0.75,
    source="test",
):
    from datetime import datetime, timezone
    from crypto_rsi_scanner.event_models import NormalizedEvent

    return NormalizedEvent(
        event_id=event_id,
        raw_ids=(event_id,),
        event_name=title,
        event_type=event_type,
        event_time=event_time,
        event_time_confidence=event_time_confidence,
        first_seen_time=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
        source=source,
        source_urls=(f"https://example.test/{event_id}",),
        external_asset=external_asset,
        description=body or None,
        confidence=confidence,
        event_time_source="explicit" if event_time else None,
    )


def _event_discovery_fixture_result():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    assets = load_asset_aliases(aliases_path)
    return event_discovery.run_discovery(raw, assets, now=now)


def _full_event_discovery_fixture_result():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery

    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    cryptopanic_path, gdelt_path, blog_path = _news_fixture_paths()
    ipo_path, sports_path, prediction_path = _external_catalyst_fixture_paths()
    tokenomist_supply_path, etherscan_supply_path, arkham_supply_path, dune_supply_path = _supply_fixture_paths()
    cfg = event_discovery.EventDiscoveryConfig(lookback_hours=120, horizon_days=2)
    return event_discovery.run_manual_discovery(
        events_path,
        aliases_path,
        binance_announcements_path=binance_path,
        bybit_announcements_path=bybit_path,
        coinmarketcal_path=coinmarketcal_path,
        tokenomist_path=tokenomist_path,
        cryptopanic_path=cryptopanic_path,
        gdelt_path=gdelt_path,
        project_blog_rss_path=blog_path,
        external_ipo_path=ipo_path,
        sports_fixtures_path=sports_path,
        prediction_market_events_path=prediction_path,
        coinalyze_derivatives_path=_derivatives_fixture_path(),
        tokenomist_supply_path=tokenomist_supply_path,
        etherscan_supply_path=etherscan_supply_path,
        arkham_supply_path=arkham_supply_path,
        dune_supply_path=dune_supply_path,
        universe_path=_coingecko_universe_fixture_path(),
        cfg=cfg,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )


def _full_event_discovery_config_values():
    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    cryptopanic_path, gdelt_path, blog_path = _news_fixture_paths()
    ipo_path, sports_path, prediction_path = _external_catalyst_fixture_paths()
    tokenomist_supply_path, etherscan_supply_path, arkham_supply_path, dune_supply_path = _supply_fixture_paths()
    return {
        "EVENT_DISCOVERY_EVENTS_PATH": events_path,
        "EVENT_DISCOVERY_ALIASES_PATH": aliases_path,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH": binance_path,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE": False,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH": bybit_path,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE": False,
        "EVENT_DISCOVERY_COINMARKETCAL_PATH": coinmarketcal_path,
        "EVENT_DISCOVERY_TOKENOMIST_PATH": tokenomist_path,
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH": cryptopanic_path,
        "EVENT_DISCOVERY_CRYPTOPANIC_LIVE": False,
        "EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN": "",
        "EVENT_DISCOVERY_GDELT_PATH": gdelt_path,
        "EVENT_DISCOVERY_GDELT_LIVE": False,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH": blog_path,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": False,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS": (),
        "EVENT_DISCOVERY_EXTERNAL_IPO_PATH": ipo_path,
        "EVENT_DISCOVERY_SPORTS_FIXTURES_PATH": sports_path,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH": prediction_path,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": False,
        "EVENT_DISCOVERY_COINALYZE_DERIVATIVES_PATH": _derivatives_fixture_path(),
        "EVENT_DISCOVERY_COINALYZE_LIVE": False,
        "EVENT_DISCOVERY_TOKENOMIST_SUPPLY_PATH": tokenomist_supply_path,
        "EVENT_DISCOVERY_ETHERSCAN_SUPPLY_PATH": etherscan_supply_path,
        "EVENT_DISCOVERY_ARKHAM_SUPPLY_PATH": arkham_supply_path,
        "EVENT_DISCOVERY_DUNE_SUPPLY_PATH": dune_supply_path,
        "EVENT_DISCOVERY_UNIVERSE_PATH": _coingecko_universe_fixture_path(),
        "EVENT_DISCOVERY_UNIVERSE_LIVE": False,
        "EVENT_SOURCE_ENRICHMENT_ENABLED": False,
        "EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN": 0,
        "EVENT_DISCOVERY_LOOKBACK_HOURS": 120,
        "EVENT_DISCOVERY_HORIZON_DAYS": 2,
        "EVENT_RESEARCH_NOW": "2026-06-15T16:00:00Z",
    }




































































































def _llm_golden_result():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    path = _llm_golden_fixture_path()
    raw = ManualJsonEventProvider(path, required=True).fetch_events(
        datetime(2026, 6, 15, tzinfo=timezone.utc),
        datetime(2026, 6, 21, tzinfo=timezone.utc),
    )
    assets = load_asset_aliases(path)
    return event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )


def _llm_packet_for(result, event_id, coin_id):
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alerts, event_llm_analyzer

    alerts = event_alerts.build_event_alert_candidates(
        result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    raw_by_id = {raw.raw_id: raw for raw in result.raw_events}
    links_by_event = {}
    for link in result.links:
        links_by_event.setdefault(link.event_id, []).append(link)
    candidates = {
        (candidate.event.event_id, candidate.asset.coin_id): candidate
        for candidate in result.candidates
    }
    alert_by_key = {
        (alert.discovery_candidate.event.event_id, alert.discovery_candidate.asset.coin_id): alert
        for alert in alerts
    }
    key = (event_id, coin_id)
    candidate = candidates[key]
    return event_llm_analyzer.build_evidence_packet(
        candidate,
        raw_by_id=raw_by_id,
        links=links_by_event.get(event_id, ()),
        alert=alert_by_key[key],
    )


def _llm_golden_alerts_and_rows(min_prefilter_score=0):
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alerts, event_llm_analyzer
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMRelationshipProvider

    result = _llm_golden_result()
    alerts = event_alerts.build_event_alert_candidates(
        result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    rows = event_llm_analyzer.analyze_event_candidates(
        result,
        alerts,
        FixtureLLMRelationshipProvider(_llm_golden_fixture_path(), required=True),
        cfg=event_llm_analyzer.EventLLMConfig(
            min_prefilter_score=min_prefilter_score,
            max_candidates_per_run=50,
        ),
    )
    return result, alerts, rows












































def _llm_extraction_rows():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_llm_extractor
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMExtractionProvider

    path = _llm_extraction_golden_fixture_path()
    raw_events = ManualJsonEventProvider(path, required=True).fetch_events(
        datetime(2026, 6, 15, tzinfo=timezone.utc),
        datetime(2026, 6, 21, tzinfo=timezone.utc),
    )
    rows = event_llm_extractor.analyze_raw_events(
        raw_events,
        FixtureLLMExtractionProvider(path, required=True),
        cfg=event_llm_extractor.EventLLMExtractorConfig(max_events_per_run=50),
    )
    return raw_events, rows










































































































































































































































































































































































































def test_conviction_monotonic_with_severity():
    base = {"flag": "OB", "rsi_z": 0.0, "volume_ratio": 1.0}
    watch = conviction_score({**base, "severity": "WATCH"})
    alert = conviction_score({**base, "severity": "ALERT"})
    extreme = conviction_score({**base, "severity": "EXTREME"})
    assert watch < alert < extreme


def test_conviction_rewards_confluence():
    weak = conviction_score({"flag": "OB", "severity": "WATCH"})
    strong = conviction_score({
        "flag": "OB",
        "severity": "WATCH",
        "rsi_4h": 75,
        "rsi_weekly": 72,
        "volume_ratio": 2.0,
        "divergence": "bearish",
        "rsi_z": 2.5,
    })
    assert strong > weak
    assert 0 <= strong <= 100


def test_conviction_uses_edge_prior_when_setup_known():
    favorable = conviction_score({
        "flag": "OS", "severity": "WATCH", "setup_type": "dip_buy",
        "market_aligned": "favorable", "rsi_z": 0.0, "volume_ratio": 1.0,
    })
    adverse = conviction_score({
        "flag": "OS", "severity": "WATCH", "setup_type": "dip_buy",
        "market_aligned": "adverse", "rsi_z": 0.0, "volume_ratio": 1.0,
    })
    no_edge = conviction_score({
        "flag": "OS", "severity": "WATCH", "setup_type": "breakdown_risk",
        "market_aligned": "adverse", "rsi_z": 0.0, "volume_ratio": 1.0,
    })
    assert favorable > adverse > no_edge


def test_conviction_unflagged_is_zero():
    assert conviction_score({"flag": "", "severity": ""}) == 0


# --- pre-alert flag decision -------------------------------------------------

def test_decide_flag_crossed():
    assert decide_flag(72, 5, 70, 30, 5, 3) == "OB"
    assert decide_flag(25, -5, 70, 30, 5, 3) == "OS"


def test_decide_flag_pre_ob_requires_momentum():
    # within margin (67 in [65,70)) and rising fast -> PRE_OB
    assert decide_flag(67, 4, 70, 30, 5, 3) == "PRE_OB"
    # same level but not moving toward -> no flag
    assert decide_flag(67, 1, 70, 30, 5, 3) == ""


def test_decide_flag_pre_os():
    assert decide_flag(33, -4, 70, 30, 5, 3) == "PRE_OS"
    assert decide_flag(33, 0, 70, 30, 5, 3) == ""


def test_decide_flag_neutral():
    assert decide_flag(50, 1, 70, 30, 5, 3) == ""


def test_decide_flag_adaptive_threshold():
    # a coin whose effective OB is 64 flags OB at 65 even though < 70
    assert decide_flag(65, 2, 64, 30, 5, 3) == "OB"


# --- tier routing ------------------------------------------------------------

def test_classify_tier_instant_on_severity():
    assert classify_tier("OB", "EXTREME", 40) == "INSTANT"
    assert classify_tier("OB", "ALERT", 10) == "INSTANT"


def test_classify_tier_instant_on_conviction():
    assert classify_tier("OB", "WATCH", 80) == "INSTANT"


def test_classify_tier_digest_low_conviction_watch():
    assert classify_tier("OB", "WATCH", 30) == "DIGEST"


def test_classify_tier_pre_always_digest():
    assert classify_tier("PRE_OB", "APPROACHING", 99) == "DIGEST"
    assert classify_tier("PRE_OS", "APPROACHING", 99) == "DIGEST"


def test_conviction_approaching_below_watch():
    appr = conviction_score({"flag": "PRE_OB", "severity": "APPROACHING"})
    watch = conviction_score({"flag": "OB", "severity": "WATCH"})
    assert appr < watch


# --- trend regime ------------------------------------------------------------

def test_regime_unknown_when_short():
    s = pd.Series(np.arange(50, dtype=float))
    assert trend_regime(s, 50, 200, 20) == "UNKNOWN"


def test_regime_uptrend():
    # steadily rising over 260 bars: price > 200MA, 50MA > 200MA, slope up
    s = pd.Series(np.linspace(10, 110, 260))
    assert trend_regime(s, 50, 200, 20) == "UPTREND"


def test_regime_downtrend():
    s = pd.Series(np.linspace(110, 10, 260))
    assert trend_regime(s, 50, 200, 20) == "DOWNTREND"


def test_regime_range():
    # oscillating with no net drift -> neither aligned up nor down
    x = np.arange(260)
    s = pd.Series(50 + 5 * np.sin(x / 5.0))
    assert trend_regime(s, 50, 200, 20) == "RANGE"


def test_regime_note_direction_matters():
    assert regime_note("OB", "UPTREND") == "continuation"
    assert regime_note("OB", "DOWNTREND") == "reversal?"
    assert regime_note("OS", "UPTREND") == "dip?"
    assert regime_note("OS", "DOWNTREND") == "continuation"
    # pre-states map to their direction
    assert regime_note("PRE_OB", "RANGE") == "range-top"
    assert regime_note("PRE_OS", "RANGE") == "range-bottom"


def test_regime_note_empty_when_unknown_or_unflagged():
    assert regime_note("OB", "UNKNOWN") == ""
    assert regime_note("", "UPTREND") == ""


# --- setup taxonomy (split signal intent) ------------------------------------

def test_signal_registry_definitions_cover_core_setups():
    from crypto_rsi_scanner import signal_registry as reg
    assert set(reg.SETUPS) == {
        "mean_reversion", "dip_buy", "trend_continuation", "breakdown_risk",
    }
    assert reg.signal_for("OB", "UPTREND").setup_type == "trend_continuation"
    assert reg.signal_for("OS", "DOWNTREND").expected_dir == "down"
    assert reg.edge_conviction_prior("dip_buy", "favorable") > reg.edge_conviction_prior("dip_buy", "adverse")
    assert reg.edge_conviction_prior("breakdown_risk", "favorable") == reg.edge_conviction_prior("breakdown_risk", "adverse")


def test_signal_registry_loads_explicit_prior_overrides():
    import json
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import signal_registry as reg

    path = Path(tempfile.mkdtemp()) / "registry_priors.json"
    path.write_text(json.dumps({
        "schema": 1,
        "setups": {
            "dip_buy": {"edge_priors": {"favorable": 73, "neutral": 41, "adverse": 11}},
            "breakdown_risk": {"edge_priors": {"adverse": 99, "no_edge": 19}},
        },
    }))
    overrides = reg.load_prior_overrides(path, strict=True)

    assert reg.edge_conviction_prior("dip_buy", "favorable", overrides=overrides) == 73
    assert reg.edge_conviction_prior("dip_buy", "adverse", overrides=overrides) == 11
    # Context-only setups still read the no_edge prior, never an alignment key.
    assert reg.edge_conviction_prior("breakdown_risk", "adverse", overrides=overrides) == 19


def test_setup_for_mapping():
    from crypto_rsi_scanner.indicators import setup_for
    assert setup_for("OB", "UPTREND") == ("trend_continuation", "up")
    assert setup_for("OS", "UPTREND") == ("dip_buy", "up")
    assert setup_for("OS", "DOWNTREND") == ("breakdown_risk", "down")
    assert setup_for("OB", "DOWNTREND") == ("mean_reversion", "down")
    assert setup_for("OB", "RANGE") == ("mean_reversion", "down")
    assert setup_for("OS", "RANGE") == ("mean_reversion", "up")
    # pre-states collapse to their direction
    assert setup_for("PRE_OB", "UPTREND") == ("trend_continuation", "up")
    assert setup_for("PRE_OS", "DOWNTREND") == ("breakdown_risk", "down")
    # unknown / missing regime -> base mean-reversion read
    assert setup_for("OB", "UNKNOWN") == ("mean_reversion", "down")
    assert setup_for("OS", "") == ("mean_reversion", "up")
    assert setup_for("", "UPTREND") == ("", "")


def test_favorable_by_direction():
    from crypto_rsi_scanner.outcomes import favorable
    assert favorable("up", 5.0) == 1 and favorable("up", -5.0) == 0
    assert favorable("down", -5.0) == 1 and favorable("down", 5.0) == 0
    # legacy flags still accepted (base mean-reversion read)
    assert favorable("OB", -5.0) == 1
    assert favorable("OS", 5.0) == 1


def test_setup_aware_grading_flips_continuation():
    # The whole point: continuation setups are graded against their OWN
    # direction, so a correct continuation no longer counts as a failed reversion.
    from crypto_rsi_scanner.indicators import setup_for
    from crypto_rsi_scanner.outcomes import favorable
    # OS in a downtrend = breakdown_risk: price falling further CONFIRMS it
    _, exp = setup_for("OS", "DOWNTREND")
    assert favorable(exp, -8.0) == 1     # was 0 under the old OS=bounce convention
    # OB in an uptrend = trend_continuation: price rising CONFIRMS it
    _, exp = setup_for("OB", "UPTREND")
    assert favorable(exp, 6.0) == 1      # was 0 under the old OB=fade convention


def test_card_headlines_setup():
    s = _sample_signal(setup_type="dip_buy", expected_dir="up")
    out = formatting.telegram_html("instant", [s], "t")
    assert "Dip Buy" in out and "expecting upside" in out


# --- market-regime gating ----------------------------------------------------

def test_market_alignment_mapping():
    from crypto_rsi_scanner.indicators import market_alignment
    assert market_alignment("dip_buy", "UPTREND") == "favorable"
    assert market_alignment("dip_buy", "BULL") == "favorable"  # backtest label
    assert market_alignment("trend_continuation", "UPTREND") == "favorable"
    assert market_alignment("mean_reversion", "RANGE") == "favorable"
    assert market_alignment("mean_reversion", "CHOP") == "favorable"  # backtest label
    assert market_alignment("mean_reversion", "UPTREND") == "adverse"
    assert market_alignment("dip_buy", "DOWNTREND") == "adverse"
    assert market_alignment("dip_buy", "BEAR") == "adverse"  # backtest label
    assert market_alignment("trend_continuation", "RANGE") == "adverse"
    # breakdown_risk: no edge anywhere -> never favorable
    assert market_alignment("breakdown_risk", "DOWNTREND") == "adverse"
    assert market_alignment("breakdown_risk", "RANGE") == "adverse"
    # neutral cells / unknown / unflagged
    assert market_alignment("mean_reversion", "DOWNTREND") == "neutral"
    assert market_alignment("dip_buy", "UNKNOWN") == "neutral"
    assert market_alignment("", "UPTREND") == "neutral"


def test_setup_has_edge():
    from crypto_rsi_scanner.indicators import setup_has_edge
    assert setup_has_edge("mean_reversion") and setup_has_edge("dip_buy")
    assert not setup_has_edge("breakdown_risk")
    assert not setup_has_edge("")


def test_market_conviction_adjustment():
    from crypto_rsi_scanner.indicators import market_conviction_adjustment
    assert market_conviction_adjustment(50, "favorable", 12) == 62
    assert market_conviction_adjustment(50, "adverse", 12) == 38
    assert market_conviction_adjustment(50, "neutral", 12) == 50
    assert market_conviction_adjustment(95, "favorable", 12) == 100   # clamped
    assert market_conviction_adjustment(5, "adverse", 12) == 0        # clamped


def test_classify_tier_market_gating():
    from crypto_rsi_scanner.scanner import classify_tier
    # adverse setup that would normally be INSTANT (ALERT) -> held to digest
    assert classify_tier("OB", "ALERT", 80, "adverse") == "DIGEST"
    # ...unless it's an outright extreme
    assert classify_tier("OB", "EXTREME", 80, "adverse") == "INSTANT"
    # favorable / neutral unaffected; default arg preserves old behavior
    assert classify_tier("OB", "ALERT", 10, "favorable") == "INSTANT"
    assert classify_tier("OB", "WATCH", 80, "neutral") == "INSTANT"
    assert classify_tier("OB", "ALERT", 10) == "INSTANT"


def test_card_shows_market_alignment():
    s = _sample_signal(setup_type="dip_buy", expected_dir="up",
                       market_regime="UPTREND", market_aligned="favorable")
    out = formatting.telegram_html("instant", [s], "t")
    assert "Bull market" in out and "favors this setup" in out


def test_card_mutes_no_edge_setup():
    s = _sample_signal(setup_type="breakdown_risk", expected_dir="down",
                       market_regime="DOWNTREND", market_aligned="adverse")
    out = formatting.telegram_html("instant", [s], "t")
    assert "no historical edge" in out
    assert "expecting downside" not in out      # direction muted
    assert "Bear market" in out and "little edge" in out


def test_storage_save_signal_roundtrip():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    st = Storage(Path(tempfile.mkdtemp()) / "s.db")
    scan_id = st.save_scan(10, 2, 1)
    st.save_signal(scan_id, {
        "symbol": "BTC", "coin_id": "bitcoin", "flag": "OB", "severity": "ALERT",
        "rsi_daily": 75.0, "conviction": 60, "tier": "INSTANT", "regime": "UPTREND",
        "setup_type": "trend_continuation", "expected_dir": "up",
        "market_regime": "UPTREND", "market_aligned": "favorable",
        "price": 70000.0, "is_new": 1,
        "state_json": '{"version":1}',
    })
    row = st.conn.execute(
        "SELECT symbol, market_regime, market_aligned, setup_type, state_json FROM signals"
    ).fetchone()
    assert row["symbol"] == "BTC" and row["market_regime"] == "UPTREND"
    assert row["market_aligned"] == "favorable"
    assert row["setup_type"] == "trend_continuation"
    assert row["state_json"] == '{"version":1}'
    assert st.recent_signal_coin_ids("2020-01-01T00:00:00+00:00") == ["bitcoin"]
    st.close()


def test_scanner_state_context_is_shadow_only():
    import json
    from crypto_rsi_scanner import scanner

    idx = pd.date_range("2025-01-01", periods=240, freq="D", tz="UTC")
    rng = np.random.RandomState(42)
    btc = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.001, 0.03, len(idx)))), index=idx)
    eth = pd.Series(80 * np.exp(np.cumsum(rng.normal(0.001, 0.035, len(idx)))), index=idx)
    coin = pd.Series(20 * np.exp(np.cumsum(rng.normal(0.001, 0.05, len(idx)))), index=idx)
    vols = pd.Series(np.linspace(8_000_000, 12_000_000, len(idx)), index=idx)
    btc_vols = pd.Series(np.linspace(500_000_000, 650_000_000, len(idx)), index=idx)
    eth_vols = pd.Series(np.linspace(300_000_000, 400_000_000, len(idx)), index=idx)
    daily = {
        "bitcoin": (btc, btc_vols),
        "ethereum": (eth, eth_vols),
        "shadowcoin": (coin, vols),
    }
    market = {
        "id": "shadowcoin", "symbol": "shd", "name": "ShadowCoin",
        "current_price": float(coin.iloc[-1]), "market_cap": 300_000_000,
        "total_volume": 12_000_000, "market_cap_rank": 123,
    }
    coin_map = {
        "bitcoin": {"id": "bitcoin", "symbol": "btc", "market_cap": 1_000_000_000_000},
        "ethereum": {"id": "ethereum", "symbol": "eth", "market_cap": 500_000_000_000},
        "shadowcoin": market,
    }
    base = scanner._analyze_coin(coin, vols, None, btc, market, "UPTREND")
    ctx = scanner._build_state_context(daily, coin_map, btc, eth)
    shadow = scanner._analyze_coin(coin, vols, None, btc, market, "UPTREND", ctx)

    assert base is not None and shadow is not None
    for key in ("flag", "setup_type", "expected_dir", "market_aligned", "conviction", "tier"):
        assert shadow[key] == base[key]
    assert shadow["vol_state"] in {"unknown", "low_compressed", "normal", "high", "high_expanding", "crisis"}
    assert shadow["breadth_state"] == json.loads(shadow["state_json"])["breadth"]["state"]
    assert set(("rs_bucket", "liquidity_bucket", "falling_knife_score")).issubset(shadow)


def test_format_signal_adds_compact_state_tokens():
    from crypto_rsi_scanner import scanner

    s = _sample_signal(
        vol_state="crisis",
        breadth_state="washout",
        rs_bucket="low",
        liquidity_bucket="low",
        falling_knife_score=82,
    )
    line = scanner._format_signal(s, is_new=False)
    assert "vol-state:crisis" in line
    assert "breadth:washout" in line
    assert "RS:low" in line
    assert "liq:low" in line
    assert "knife:82" in line


def test_dry_run_csv_helper_does_not_write():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner, config

    path = Path(tempfile.mkdtemp()) / "latest.csv"
    orig = config.CSV_OUT
    config.CSV_OUT = path
    try:
        df = pd.DataFrame([{"symbol": "AAA", "sparkline": [1, 2], "state": {"x": 1}}])
        assert scanner._write_latest_csv(df, dry_run=True) is False
        assert not path.exists()
        assert scanner._write_latest_csv(df, dry_run=False) is True
        assert path.exists()
        assert "sparkline" not in path.read_text(encoding="utf-8")
    finally:
        config.CSV_OUT = orig


# --- .env loader -------------------------------------------------------------

def test_dotenv_skips_empty_values():
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner.config import _load_dotenv

    env_path = Path(tempfile.mkdtemp()) / ".env"
    env_path.write_text("RSI_TEST_FILLED=hello\nRSI_TEST_EMPTY=\n# comment\n", encoding="utf-8")

    for k in ("RSI_TEST_FILLED", "RSI_TEST_EMPTY"):
        os.environ.pop(k, None)
    try:
        _load_dotenv(env_path)
        # filled value is loaded; empty value is treated as unset (uses default)
        assert os.environ.get("RSI_TEST_FILLED") == "hello"
        assert "RSI_TEST_EMPTY" not in os.environ
    finally:
        os.environ.pop("RSI_TEST_FILLED", None)


def test_env_bool_strips_whitespace():
    from crypto_rsi_scanner.config import _env_bool

    key = "RSI_TEST_BOOL"
    old = os.environ.get(key)
    try:
        os.environ[key] = " 0 "
        assert _env_bool(key, True) is False
        os.environ[key] = " false "
        assert _env_bool(key, True) is False
        os.environ[key] = " yes "
        assert _env_bool(key, False) is True
    finally:
        if old is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old


# --- universe hygiene --------------------------------------------------------

def _market(**over):
    base = {
        "id": "bitcoin", "symbol": "btc", "name": "Bitcoin",
        "current_price": 100.0, "market_cap": 1_000_000_000.0,
        "total_volume": 20_000_000.0,
        "price_change_percentage_24h_in_currency": 2.0,
    }
    base.update(over)
    return base


def test_universe_filters_stable_wrapped_and_bad_quality():
    from crypto_rsi_scanner import universe
    cases = [
        (_market(id="tether", symbol="usdt", name="Tether"), "stable_like"),
        (_market(id="usd1-wlfi", symbol="usd1", name="USD1"), "stable_like"),
        (_market(id="global-dollar", symbol="usdg", name="Global Dollar"), "stable_like"),
        (_market(id="usdtb", symbol="usdtb", name="USDtb"), "stable_like"),
        (_market(id="bfusd", symbol="bfusd", name="BFUSD"), "stable_like"),
        (_market(id="apxusd", symbol="apxusd", name="apxUSD"), "stable_like"),
        (_market(id="united-stables", symbol="u", name="United Stables"), "stable_like"),
        (_market(id="gho", symbol="gho", name="GHO"), "stable_like"),
        (_market(id="ylds", symbol="ylds", name="YLDS"), "stable_like"),
        (_market(id="usx", symbol="usx", name="USX"), "stable_like"),
        (_market(id="tether-gold", symbol="xaut", name="Tether Gold"), "stable_like"),
        (_market(id="pax-gold", symbol="paxg", name="PAX Gold"), "stable_like"),
        (_market(id="wrapped-bitcoin", symbol="wbtc", name="Wrapped Bitcoin"), "excluded_symbol"),
        (_market(id="bridged-eth", symbol="beth", name="Bridged ETH"), "wrapped_staked_or_synthetic"),
        (_market(id="thin", symbol="thin", name="Thin", total_volume=10.0), "low_liquidity"),
        (_market(id="bad", symbol="bad", name="Bad", price_change_percentage_24h_in_currency=900.0), "suspicious_24h_move"),
    ]
    for market, reason in cases:
        assert universe.exclusion_reason(market) == reason


def test_universe_keeps_stacks_and_limits_clean_results():
    from crypto_rsi_scanner import universe
    markets = [
        _market(id="tether", symbol="usdt", name="Tether"),
        _market(id="blockstack", symbol="stx", name="Stacks"),
        _market(id="ethereum", symbol="eth", name="Ethereum"),
    ]
    kept, excluded = universe.filter_markets(markets, limit=1)
    assert [m["symbol"] for m in kept] == ["stx"]
    assert excluded["stable_like"] == 1


def test_universe_candidate_count_overfetches():
    from crypto_rsi_scanner import universe
    assert universe.candidate_count(20) > 20
    assert universe.candidate_count(500) <= 250


def test_universe_audit_keeps_exclusion_examples_after_limit():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import universe

    markets = [
        _market(id="blockstack", symbol="stx", name="Stacks"),
        _market(id="tether", symbol="usdt", name="Tether"),
        _market(id="thin", symbol="thin", name="Thin", total_volume=10.0),
    ]
    kept, excluded, audit = universe.filter_markets_with_audit(
        markets,
        limit=1,
        now=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )
    assert [m["symbol"] for m in kept] == ["stx"]
    assert excluded["stable_like"] == 1
    assert excluded["low_liquidity"] == 1
    assert audit["kept_count"] == 1
    assert audit["excluded_count"] == 2
    assert {x["reason"] for x in audit["excluded_examples"]} == {"stable_like", "low_liquidity"}
    assert "UNIVERSE HYGIENE AUDIT" in universe.format_audit(audit)


def test_universe_audit_flags_suspicious_kept_rows():
    from crypto_rsi_scanner import universe

    audit = {
        "kept": [
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "rank": 1},
            {"id": "example-yield", "symbol": "yield", "name": "Example Yield", "rank": 99},
        ],
        "excluded_by_reason": {},
    }
    leaks = universe.suspicious_kept(audit)
    assert [x["symbol"] for x in leaks] == ["yield"]
    assert "suspicious kept" in universe.format_audit(audit)

    markets = [
        {
            "id": f"plain-{i}",
            "symbol": f"p{i}",
            "name": f"Plain {i}",
            "market_cap": 1_000_000_000,
            "total_volume": 20_000_000,
            "market_cap_rank": i + 1,
        }
        for i in range(90)
    ]
    markets.append({
        "id": "example-yield",
        "symbol": "yield",
        "name": "Example Yield",
        "market_cap": 900_000_000,
        "total_volume": 20_000_000,
        "market_cap_rank": 99,
    })
    _, _, full_audit = universe.filter_markets_with_audit(markets, limit=100)
    assert len(full_audit["kept"]) == 91
    assert universe.suspicious_kept(full_audit)[0]["symbol"] == "yield"


def test_scanner_fetch_universe_audit_uses_shared_filter():
    import asyncio
    from crypto_rsi_scanner import scanner

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get_top_markets(self, n):
            assert n >= 2
            return [
                _market(id="blockstack", symbol="stx", name="Stacks"),
                _market(id="usd1-wlfi", symbol="usd1", name="USD1"),
            ]

    orig = scanner.CoinGeckoClient
    scanner.CoinGeckoClient = FakeClient
    try:
        audit = asyncio.run(scanner.fetch_universe_audit(top_n=1))
    finally:
        scanner.CoinGeckoClient = orig

    assert audit["kept_count"] == 1
    assert audit["kept"][0]["symbol"] == "stx"
    assert audit["excluded_by_reason"] == {"stable_like": 1}


# --- telegram formatting -----------------------------------------------------

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


def test_telegram_instant_has_html_and_emoji():
    s = _sample_signal(flag="OB", severity="EXTREME", conviction=93)
    out = formatting.telegram_html("instant", [s], "2026-05-31 19:59 UTC")
    assert "⚡" in out
    assert "<b>BNB</b>" in out
    assert "Conviction <b>93</b>/100" in out
    assert "RSI <b>73</b>" in out  # 72.7 -> 73


def test_telegram_digest_groups_by_direction():
    sigs = [
        _sample_signal(symbol="AAA", flag="OB"),
        _sample_signal(symbol="BBB", flag="OS", regime="DOWNTREND", regime_note="continuation"),
        _sample_signal(symbol="CCC", flag="PRE_OS", severity="APPROACHING", regime_note="continuation"),
    ]
    out = formatting.telegram_html("digest", sigs, "t")
    assert "Overbought" in out and "Oversold" in out and "Approaching" in out
    assert "<b>AAA</b>" in out and "<b>CCC</b>" in out


def test_telegram_escapes_special_chars():
    s = _sample_signal(symbol="A&B<X>")
    out = formatting.telegram_html("instant", [s], "t")
    assert "A&amp;B&lt;X&gt;" in out
    assert "<b>A&B<X></b>" not in out  # raw must not leak


def test_chart_link_escapes_quotes_in_href():
    s = _sample_signal(symbol='A&B<X>"')
    out = formatting.telegram_html("instant", [s], "t")
    assert 'symbol=A&amp;B&lt;X&gt;&quot;USDT' in out
    assert 'symbol=A&B<X>"USDT' not in out


def test_telegram_handles_missing_4h_nan():
    s = _sample_signal(rsi_4h=float("nan"))
    out = formatting.telegram_html("instant", [s], "t")
    assert "4H" not in out  # NaN timeframe omitted, no crash


def test_plain_text_uses_line():
    s = _sample_signal(line="  BNB . c50 stuff")
    out = formatting.plain_text("digest", [s], "t")
    assert "BNB . c50 stuff" in out


# --- signal outcome tracking -------------------------------------------------

def test_favorable_convention():
    from crypto_rsi_scanner.outcomes import favorable
    assert favorable("OB", -5.0) == 1   # overbought + price fell = good
    assert favorable("OB", 5.0) == 0
    assert favorable("OS", 5.0) == 1    # oversold + price rose = good
    assert favorable("OS", -5.0) == 0
    assert favorable("PRE_OB", -2.0) == 1


def test_price_asof():
    from datetime import datetime, timezone
    from crypto_rsi_scanner.outcomes import _price_asof
    idx = pd.date_range("2026-05-01", periods=10, freq="D", tz="UTC")
    closes = pd.Series(range(10), index=idx, dtype=float)
    # returns last value at/before the timestamp
    assert _price_asof(closes, datetime(2026, 5, 5, tzinfo=timezone.utc)) == 4.0
    assert _price_asof(pd.Series(dtype=float), datetime(2026, 5, 5, tzinfo=timezone.utc)) is None
    # before the series start -> None
    assert _price_asof(closes, datetime(2026, 4, 1, tzinfo=timezone.utc)) is None


def test_price_asof_mixed_time_units():
    # Regression: pandas 3 Series.asof() raises "Cannot losslessly convert
    # units" when index resolution (ms, from unit='ms' parsing) != Timestamp
    # resolution (us, from an isoformat string with microseconds).
    from datetime import datetime
    from crypto_rsi_scanner.outcomes import _price_asof
    idx = pd.to_datetime([1714521600000 + i * 86400000 for i in range(10)],
                         unit="ms", utc=True)  # ms-resolution index
    closes = pd.Series(range(10), index=idx, dtype=float)
    ts = datetime.fromisoformat("2026-05-02T07:08:23.760073+00:00")  # us-resolution
    val = _price_asof(closes, ts)  # must not raise
    assert val is not None and val >= 0


def test_outcome_evaluation_records_matured():
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import outcomes

    db = Path(tempfile.mkdtemp()) / "o.db"
    st = Storage(db)
    now = datetime(2026, 5, 31, tzinfo=timezone.utc)
    run_at = now - timedelta(days=10)
    st.conn.execute(
        "INSERT INTO signals (symbol, coin_id, flag, severity, price, is_new, run_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("AAA", "aaa", "OB", "ALERT", 100.0, 1, run_at.isoformat()),
    )
    st.conn.commit()

    # price 100 at entry, then declines 1/day -> OB fade is favorable
    idx = pd.date_range(end=now, periods=16, freq="D", tz="UTC")
    vals = [100.0 if (d - pd.Timestamp(run_at)).days <= 0
            else 100.0 - (d - pd.Timestamp(run_at)).days for d in idx]
    closes = pd.Series(vals, index=idx)

    n = outcomes.evaluate_coin(st, "aaa", closes, [1, 3, 7, 14], now=now)
    assert n == 3  # 1/3/7 matured; 14d not (only 10 days elapsed)
    recs = st.conn.execute(
        "SELECT horizon_days, ret_pct, favorable FROM outcomes ORDER BY horizon_days"
    ).fetchall()
    assert [r["horizon_days"] for r in recs] == [1, 3, 7]
    assert all(r["favorable"] == 1 for r in recs)
    assert abs(recs[-1]["ret_pct"] - (-7.0)) < 1e-6  # 93/100 - 1
    # idempotent: re-running records nothing new
    assert outcomes.evaluate_coin(st, "aaa", closes, [1, 3, 7, 14], now=now) == 0
    st.close()


def test_build_report_empty_and_populated():
    from crypto_rsi_scanner.outcomes import build_report
    assert "No matured" in build_report([])

    rows = [
        {"horizon_days": 7, "ret_pct": -3.0, "favorable": 1, "flag": "OB",
         "regime": "DOWNTREND", "regime_note": "reversal?", "conviction": 80,
         "symbol": "A", "severity": "ALERT", "market_regime": "DOWNTREND",
         "market_aligned": "neutral",
         "state_json": '{"volatility":{"state":"high"},"breadth":{"state":"washout"}}'},
        {"horizon_days": 7, "ret_pct": 2.0, "favorable": 0, "flag": "OB",
         "regime": "UPTREND", "regime_note": "continuation", "conviction": 55,
         "symbol": "B", "severity": "WATCH", "market_regime": "DOWNTREND",
         "market_aligned": "favorable"},
        {"horizon_days": 7, "ret_pct": 4.0, "favorable": 1, "flag": "OS",
         "regime": "DOWNTREND", "regime_note": "continuation", "conviction": 70,
         "symbol": "C", "severity": "ALERT", "market_regime": "DOWNTREND",
         "market_aligned": "adverse"},
    ]
    out = build_report(rows, primary_horizon=7)
    assert "RSI SIGNAL OUTCOMES" in out
    assert "By setup" in out and "By conviction" in out
    assert "By actionable/control" in out
    assert "By market alignment" in out
    assert "By state cohort" in out and "washout" in out


# --- subscriber management ---------------------------------------------------

def _fresh_storage():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    return Storage(Path(tempfile.mkdtemp()) / "subs.db")


def test_subscribe_add_and_dedup():
    st = _fresh_storage()
    assert st.subscribe("111", "alice") is True       # new
    assert st.subscribe("111", "alice") is False      # already active -> no-op
    assert st.active_subscribers() == ["111"]
    st.close()


def test_unsubscribe_and_resubscribe():
    st = _fresh_storage()
    st.subscribe("111", "alice")
    st.subscribe("222", "bob")
    assert st.unsubscribe("111") is True
    assert st.unsubscribe("111") is False             # already inactive
    assert st.active_subscribers() == ["222"]
    assert st.subscribe("111", None) is True          # reactivated
    assert set(st.active_subscribers()) == {"111", "222"}
    st.close()


def test_seed_from_config(monkeypatch=None):
    from crypto_rsi_scanner import telegram, config
    st = _fresh_storage()
    orig = config.TELEGRAM_CHAT_IDS
    config.TELEGRAM_CHAT_IDS = ["999", "888"]
    try:
        telegram.seed_subscribers_from_config(st)
        assert set(st.active_subscribers()) == {"999", "888"}
    finally:
        config.TELEGRAM_CHAT_IDS = orig
        st.close()


# --- richer formatting (Part A) ----------------------------------------------

def test_sparkline_basic():
    assert formatting.sparkline([1, 2, 3, 4, 5, 6, 7, 8]) == "▁▂▃▄▅▆▇█"
    assert formatting.sparkline([]) == ""
    assert formatting.sparkline([5]) == ""
    assert set(formatting.sparkline([5, 5, 5])) == {"▁"}  # flat


def test_price_formatting():
    assert formatting._fmt_price(72000) == "$72,000"
    assert formatting._fmt_price(721.09) == "$721.09"
    assert formatting._fmt_price(0.0034) == "$0.0034"


def test_instant_card_has_rich_fields():
    s = _sample_signal(price=721.09, pct_24h=8.2, pct_7d=-3.1, ath_pct=-8.5,
                       sparkline=[700, 710, 690, 720])
    out = formatting.telegram_html("instant", [s], "t")
    assert "$721.09" in out
    assert "+8.2% 24h" in out
    assert "below ATH" in out
    assert "tradingview.com" in out  # chart link
    assert "<code>" in out          # sparkline


def test_digest_line_shows_24h():
    s = _sample_signal(pct_24h=-5.0)
    out = formatting.telegram_html("digest", [s], "t")
    assert "-5%" in out


# --- inline hit-rates (Part B) ------------------------------------------------

def test_track_records_and_text():
    from crypto_rsi_scanner import outcomes
    rows = []
    # 6 OB-in-downtrend, 5 favorable -> 83%
    for i in range(6):
        rows.append({"horizon_days": 7, "ret_pct": -4.0 if i < 5 else 2.0,
                     "favorable": 1 if i < 5 else 0, "flag": "OB",
                     "regime": "DOWNTREND", "regime_note": "reversal?",
                     "conviction": 70, "symbol": f"X{i}", "severity": "ALERT"})
    stats = outcomes.track_records(rows, 7)
    assert stats["mean_reversion"]["n"] == 6   # OB-in-downtrend -> mean_reversion
    txt = outcomes.track_record_text("mean_reversion", stats, 7)
    assert "5/6" in txt and "mean reversion" in txt


def test_track_record_insufficient_samples():
    from crypto_rsi_scanner import outcomes
    rows = [{"horizon_days": 7, "ret_pct": -4.0, "favorable": 1, "flag": "OB",
             "regime": "RANGE", "regime_note": "", "conviction": 50,
             "symbol": "A", "severity": "WATCH"}]
    stats = outcomes.track_records(rows, 7)  # only 1 sample < MIN
    assert stats == {}
    assert outcomes.track_record_text("mean_reversion", stats, 7) == ""


# --- heartbeat (Part D) -------------------------------------------------------

def test_heartbeat_health_checks(monkeypatch=None):
    from crypto_rsi_scanner import heartbeat, config
    sent = []
    orig = heartbeat.send_telegram
    heartbeat.send_telegram = lambda *a, **k: sent.append(a) or True
    try:
        assert heartbeat.check_health({"requested": 90, "fetched": 88, "analyzed": 80}) is True
        assert not sent
        # degraded: >30% failed
        assert heartbeat.check_health({"requested": 90, "fetched": 50, "analyzed": 40}) is False
        # no data
        assert heartbeat.check_health({"requested": 90, "fetched": 0, "analyzed": 0}) is False
        assert len(sent) == 2
    finally:
        heartbeat.send_telegram = orig


# --- bot commands (Part C) ----------------------------------------------------

def test_snapshot_save_load():
    from crypto_rsi_scanner import telegram
    st = _fresh_storage()
    sigs = [_sample_signal(symbol="AAA", flag="OB", conviction=80),
            _sample_signal(symbol="BBB", flag="OS", conviction=40)]
    telegram.save_latest_snapshot(st, sigs)
    loaded = telegram._load_snapshot(st)
    assert {s["symbol"] for s in loaded} == {"AAA", "BBB"}
    st.close()


def test_cmd_top_and_detail():
    from crypto_rsi_scanner import telegram
    st = _fresh_storage()
    telegram.save_latest_snapshot(st, [
        _sample_signal(symbol="AAA", flag="OB", conviction=80),
        _sample_signal(symbol="BBB", flag="OS", conviction=40),
    ])
    top = telegram._cmd_top(st)
    assert "AAA" in top and "BBB" in top
    detail = telegram._cmd_detail(st, "aaa")
    assert "AAA" in detail
    assert "isn't on the current watch-list" in telegram._cmd_detail(st, "ZZZ")
    st.close()


# --- self-tuning conviction --------------------------------------------------

def test_conviction_adjustment_insufficient_samples():
    from crypto_rsi_scanner.indicators import conviction_adjustment
    # below min_samples -> unchanged
    assert conviction_adjustment(50, 0.9, 3, min_samples=8) == 50
    assert conviction_adjustment(50, None, 100, min_samples=8) == 50


def test_conviction_adjustment_direction():
    from crypto_rsi_scanner.indicators import conviction_adjustment
    # high hit rate with ample samples -> nudges up; low -> nudges down
    up = conviction_adjustment(50, 0.9, 40, min_samples=8, max_swing=15)
    down = conviction_adjustment(50, 0.1, 40, min_samples=8, max_swing=15)
    assert up > 50 and down < 50
    # 50% hit rate -> no change
    assert conviction_adjustment(50, 0.5, 40, min_samples=8) == 50


def test_conviction_adjustment_bounded():
    from crypto_rsi_scanner.indicators import conviction_adjustment
    # swing capped; never exceeds max_swing, never leaves 0..100
    assert conviction_adjustment(95, 1.0, 100, max_swing=15) <= 100
    assert conviction_adjustment(5, 0.0, 100, max_swing=15) >= 0
    hi = conviction_adjustment(50, 1.0, 1000, min_samples=8, max_swing=15)
    assert hi - 50 <= 15


def test_conviction_adjustment_confidence_scaling():
    from crypto_rsi_scanner.indicators import conviction_adjustment
    # more samples -> larger (or equal) move toward the empirical signal
    few = conviction_adjustment(50, 0.9, 8, min_samples=8, max_swing=15)
    many = conviction_adjustment(50, 0.9, 80, min_samples=8, max_swing=15)
    assert (many - 50) >= (few - 50) >= 0


# --- macro context -----------------------------------------------------------

def test_macro_header_assembles():
    from crypto_rsi_scanner import macro
    m = {
        "n_ob": 17, "n_os": 3, "d_ob": 6, "d_os": -1,
        "fng": {"value": 22, "label": "Fear"},
        "btc_regime": "DOWNTREND",
        "glob": {"btc_dominance": 54.3, "mcap_change_24h": -2.8},
    }
    line = macro.macro_header(m)
    assert "F&amp;G 22 (Fear)" in line
    assert "Downtrend" in line
    assert "breadth 17🔴" in line and "3🟢" in line
    assert "-2.8% 24h" in line


def test_macro_header_empty_safe():
    from crypto_rsi_scanner import macro
    # missing pieces are omitted, never crash; breadth always present
    line = macro.macro_header({"n_ob": 0, "n_os": 0})
    assert "breadth" in line
    assert macro.macro_header(None) == ""


def test_macro_digest_includes_header():
    s = _sample_signal()
    out = formatting.telegram_html("digest", [s], "t", macro_line="🌍 test-macro")
    assert "test-macro" in out


def test_alert_render_smoke_suite():
    from crypto_rsi_scanner import alert_smoke
    results = alert_smoke.run_smoke()
    names = {r.name for r in results}
    assert names == {"telegram_instant", "telegram_digest", "plain_instant", "plain_digest"}
    assert all(r.chars > 0 for r in results)


# --- backtester ---------------------------------------------------------------

def test_backtest_edge_zero_when_signal_matches_base():
    # The anti-tautology guarantee: a setup that confirms 100% in a regime that
    # *always* moves that way has ZERO edge — it's just "trends trend".
    from crypto_rsi_scanner import backtest
    regime_base = {("DOWNTREND", 1): [-5.0, -4.0, -6.0, -3.0]}  # P(down)=100%
    signals = [{"setup": "breakdown_risk", "exp": "down", "regime": "DOWNTREND",
                "h": 1, "ret": -5.0, "fav": 1, "conv": 60} for _ in range(4)]
    r = backtest.summarize(signals, regime_base)[0]
    assert r["conf"] == 100.0 and r["base"] == 100.0
    assert abs(r["edge"]) < 1e-9


def test_backtest_positive_edge_when_signal_beats_base():
    from crypto_rsi_scanner import backtest
    regime_base = {("DOWNTREND", 1): [-2.0, -1.0, 2.0, 1.0]}  # P(down)=50%, mean 0
    signals = [{"setup": "breakdown_risk", "exp": "down", "regime": "DOWNTREND",
                "h": 1, "ret": -3.0, "fav": 1, "conv": 60} for _ in range(5)]
    r = backtest.summarize(signals, regime_base)[0]
    assert r["conf"] == 100.0
    assert abs(r["base"] - 50.0) < 1e-9
    assert abs(r["edge"] - 50.0) < 1e-9
    assert r["med_excess"] > 0  # fell more than the regime's average day


def test_backtest_conditional_table_buckets_by_feature():
    # low-vol oversold-in-downtrend bounces (+ret); high-vol continues down (-ret).
    # The slice should show that, with edge measured vs same-vol-bucket base days.
    from crypto_rsi_scanner import backtest
    signals = []
    for v, r in [(0.1, +3.0)] * 10 + [(0.5, -1.0)] * 10 + [(0.9, -6.0)] * 10:
        signals.append({"setup": "breakdown_risk", "exp": "down", "regime": "DOWNTREND",
                        "h": 3, "ret": r, "fav": 1 if r < 0 else 0, "conv": 50,
                        "vol": v, "mom": -10.0})
    # base: each vol level falls ~50% of the time, regardless of vol
    cond_base = {("DOWNTREND", 3): [(v, -10.0, r)
                 for v in (0.1, 0.5, 0.9) for r in (-1.0, 1.0)] * 20}
    res = backtest.conditional_table(signals, cond_base, "breakdown_risk",
                                     "DOWNTREND", "down", 3, "vol")
    assert res is not None
    (q1, q2), rows = res
    assert rows[0]["sig"] < 20    # low vol -> rarely falls (bounces)
    assert rows[2]["sig"] > 80    # high vol -> keeps falling
    assert rows[2]["edge"] > 20   # and beats the same-vol-bucket base (~50%)


def test_backtest_market_regime_series():
    from crypto_rsi_scanner import backtest
    idx_up = pd.date_range("2020-01-01", periods=300, freq="D", tz="UTC")
    up = pd.Series(np.linspace(10, 110, 300), index=idx_up)
    down = pd.Series(np.linspace(110, 10, 300), index=idx_up)
    assert backtest.market_regime_series(up).iloc[-1] == "BULL"
    assert backtest.market_regime_series(down).iloc[-1] == "BEAR"
    assert backtest.market_regime_series(up).iloc[0] == "NA"  # 200d warm-up


def test_backtest_summarize_market_splits_regime():
    # mean_reversion confirms in BULL, fails in BEAR — must not blend away.
    from crypto_rsi_scanner import backtest
    signals = []
    for _ in range(10):
        signals.append({"setup": "mean_reversion", "exp": "up", "regime": "RANGE",
                        "mkt": "BULL", "h": 7, "ret": 5.0, "fav": 1, "conv": 50})
    for _ in range(10):
        signals.append({"setup": "mean_reversion", "exp": "up", "regime": "RANGE",
                        "mkt": "BEAR", "h": 7, "ret": -5.0, "fav": 0, "conv": 50})
    mkt_base = {("RANGE", "BULL", 7): [1.0, 1.0, -1.0, 1.0],   # base P(up)=75%
                ("RANGE", "BEAR", 7): [-1.0, -1.0, 1.0, -1.0]}  # base P(up)=25%
    by = {(r["setup"], r["mkt"]): r for r in backtest.summarize_market(signals, mkt_base, 7)}
    assert by[("mean_reversion", "BULL")]["conf"] == 100.0
    assert by[("mean_reversion", "BEAR")]["conf"] == 0.0
    assert abs(by[("mean_reversion", "BULL")]["edge"] - 25.0) < 1e-9   # 100 - 75
    assert abs(by[("mean_reversion", "BEAR")]["edge"] + 25.0) < 1e-9   # 0 - 25


def test_backtest_state_slices_compare_same_state_base():
    from crypto_rsi_scanner import backtest

    signals = []
    for _ in range(10):
        signals.append({"setup": "dip_buy", "exp": "up", "regime": "UPTREND",
                        "h": 7, "ret": 4.0, "fav": 1, "conv": 60,
                        "vol_state": "low_compressed", "breadth_state": "neutral",
                        "rs_bucket": "high", "liquidity_bucket": "high",
                        "knife_bucket": "low"})
    for _ in range(10):
        signals.append({"setup": "dip_buy", "exp": "up", "regime": "UPTREND",
                        "h": 7, "ret": -4.0, "fav": 0, "conv": 60,
                        "vol_state": "crisis", "breadth_state": "breadth_collapse",
                        "rs_bucket": "low", "liquidity_bucket": "low",
                        "knife_bucket": "high"})

    state_base = {
        ("UPTREND", "vol_state", "low_compressed", 7): [1.0, -1.0] * 20,
        ("UPTREND", "vol_state", "crisis", 7): [1.0, -1.0] * 20,
        ("UPTREND", "rs_bucket", "high", 7): [1.0, -1.0] * 20,
        ("UPTREND", "rs_bucket", "low", 7): [1.0, -1.0] * 20,
        ("UPTREND", "liquidity_bucket", "high", 7): [1.0, -1.0] * 20,
        ("UPTREND", "liquidity_bucket", "low", 7): [1.0, -1.0] * 20,
        ("UPTREND", "knife_bucket", "low", 7): [1.0, -1.0] * 20,
        ("UPTREND", "knife_bucket", "high", 7): [1.0, -1.0] * 20,
        ("UPTREND", "breadth_state", "neutral", 7): [1.0, -1.0] * 20,
        ("UPTREND", "breadth_state", "breadth_collapse", 7): [1.0, -1.0] * 20,
    }
    rows = backtest.summarize_state_slices(signals, state_base, 7, min_n=8)
    by = {(r["feature"], r["bucket"]): r for r in rows}
    assert by[("vol_state", "low_compressed")]["edge"] == 50.0
    assert by[("vol_state", "crisis")]["edge"] == -50.0
    assert by[("knife_bucket", "high")]["med_dir"] < 0
    text = backtest.format_state_slices(signals, state_base, 7, min_n=8)
    assert "State-conditioned edge slices" in text
    assert "falling-knife bucket" in text


def test_backtest_build_state_frames_contains_shadow_labels():
    from crypto_rsi_scanner import backtest

    idx = pd.date_range("2025-01-01", periods=280, freq="D", tz="UTC")
    btc = pd.DataFrame({
        "close": pd.Series(np.linspace(100, 180, len(idx)), index=idx),
        "volume": pd.Series(1_000.0, index=idx),
    })
    weak = pd.DataFrame({
        "close": pd.Series(np.linspace(80, 30, len(idx)), index=idx),
        "volume": pd.Series(np.linspace(20_000, 40_000, len(idx)), index=idx),
    })
    frames = {"BTC": btc, "WEAK": weak}
    state = backtest.build_state_frames(frames)
    assert set(state) == {"BTC", "WEAK"}
    cols = set(state["WEAK"].columns)
    assert {"vol_state", "breadth_state", "rs_bucket", "liquidity_bucket",
            "falling_knife_score", "knife_bucket"}.issubset(cols)
    assert state["WEAK"]["rs_bucket"].iloc[-1] in {"low", "mid", "high"}


def test_backtest_builds_registry_prior_calibration():
    from crypto_rsi_scanner import backtest, signal_registry as reg

    signals = []
    # Favorable dip-buy in BULL: 100% confirms vs 50% base -> prior should rise.
    for _ in range(16):
        signals.append({"setup": "dip_buy", "exp": "up", "regime": "UPTREND",
                        "mkt": "BULL", "h": 7, "ret": 4.0, "fav": 1, "conv": 60})
    # Adverse dip-buy in BEAR: 0% confirms vs 50% base -> prior should fall.
    for _ in range(16):
        signals.append({"setup": "dip_buy", "exp": "up", "regime": "UPTREND",
                        "mkt": "BEAR", "h": 7, "ret": -4.0, "fav": 0, "conv": 60})
    # Breakdown risk can have apparent edge in evidence, but it must stay context-only.
    for _ in range(16):
        signals.append({"setup": "breakdown_risk", "exp": "down", "regime": "DOWNTREND",
                        "mkt": "BEAR", "h": 7, "ret": -4.0, "fav": 1, "conv": 40})

    mkt_base = {
        ("UPTREND", "BULL", 7): [1.0, -1.0] * 20,
        ("UPTREND", "BEAR", 7): [1.0, -1.0] * 20,
        ("DOWNTREND", "BEAR", 7): [1.0, -1.0] * 20,
    }

    payload = backtest.build_registry_prior_export(
        signals, mkt_base, n_coins=3, days=365, source="unit-test", min_samples=8
    )
    priors = payload["setups"]["dip_buy"]["edge_priors"]
    defaults = reg.SETUPS["dip_buy"].edge_priors
    assert priors["favorable"] > defaults["favorable"]
    assert priors["adverse"] < defaults["adverse"]
    assert payload["setups"]["breakdown_risk"]["edge_priors"]["no_edge"] == (
        reg.SETUPS["breakdown_risk"].edge_priors["no_edge"]
    )
    assert "context_only_no_edge_not_auto_promoted" in payload["setups"]["breakdown_risk"]["notes"]


def test_backtest_cost_and_walk_forward_reports():
    from crypto_rsi_scanner import backtest

    idx = pd.date_range("2026-01-01", periods=8, freq="D", tz="UTC")
    signals = []
    for i, ts in enumerate(idx):
        setup = "dip_buy" if i % 2 == 0 else "breakdown_risk"
        exp = "up" if setup == "dip_buy" else "down"
        ret = 2.0 if setup == "dip_buy" else -1.0
        signals.append({
            "setup": setup,
            "exp": exp,
            "regime": "UPTREND" if setup == "dip_buy" else "DOWNTREND",
            "h": 7,
            "ret": ret,
            "fav": 1,
            "conv": 70 - i,
            "mkt": "BULL" if setup == "dip_buy" else "BEAR",
            "ts": ts,
            "symbol": f"T{i}",
            "liquidity_bucket": "low" if i == 0 else "high",
        })

    costs = backtest.format_cost_report(
        signals, fee_bps=10, slippage_bps=20, max_trades_per_day=1
    )
    assert "Cost-aware backtest book" in costs
    assert "actionable" in costs
    assert "dip_buy" in costs

    wf = backtest.format_walk_forward(signals, folds=4)
    assert "Walk-forward setup stability" in wf
    assert "Train = all earlier folds" in wf

    mkt_base = {
        ("UPTREND", "BULL", 7): [1.0, -1.0] * 10,
        ("DOWNTREND", "BEAR", 7): [1.0, -1.0] * 10,
    }
    mkt_wf = backtest.format_market_walk_forward(signals, mkt_base, folds=4, min_test_n=1)
    assert "Walk-forward setup × MARKET regime stability" in mkt_wf
    assert "Base = full-period same coin-regime × BTC-market base" in mkt_wf
    assert "dip_buy" in mkt_wf
    assert "BULL" in mkt_wf
    assert "+50" in mkt_wf


def test_backtest_pit_membership():
    # Point-in-time top-2: a coin that's big early then shrinks should be a
    # member only while it ranks in the top-2 by mcap on each date.
    from crypto_rsi_scanner import backtest
    idx = pd.date_range("2025-01-01", periods=4, freq="D", tz="UTC")
    histories = {
        "big":   pd.DataFrame({"mcap": [100, 100, 100, 100]}, index=idx),
        "faller": pd.DataFrame({"mcap": [90, 90, 10, 10]}, index=idx),   # drops out
        "riser": pd.DataFrame({"mcap": [5, 5, 80, 80]}, index=idx),      # climbs in
    }
    member = backtest.build_pit_membership(histories, top_n=2)
    assert list(member["big"]) == [True, True, True, True]
    assert list(member["faller"]) == [True, True, False, False]
    assert list(member["riser"]) == [False, False, True, True]


def test_backtest_volume_membership_rolling_rank():
    # Membership = top-N by TRAILING mean dollar volume: needs `window` days of
    # history to enter (no lookahead), and rank flips follow the trailing mean.
    from crypto_rsi_scanner import backtest
    idx = pd.date_range("2025-01-01", periods=6, freq="D", tz="UTC")
    frames = {
        "BIG": pd.DataFrame({"quote_volume": [100.0] * 6}, index=idx),
        "FADE": pd.DataFrame({"quote_volume": [90, 90, 1, 1, 1, 1]}, index=idx),
        "RISE": pd.DataFrame({"quote_volume": [1, 1, 95, 95, 95, 95]}, index=idx),
    }
    m = backtest.build_volume_membership(frames, top_n=2, window=2)
    # day 0: trailing-2 mean undefined for everyone -> nobody is a member
    assert not m.iloc[0].any()
    assert list(m["BIG"])[1:] == [True] * 5
    # FADE trailing means: 90, 45.5, 1, 1, 1 — loses rank 2 to RISE (48) on day 2
    assert list(m["FADE"])[1:] == [True, False, False, False, False]
    # RISE trailing means: 1, 48, 95, 95, 95 — enters as soon as its ramp shows up
    assert list(m["RISE"])[1:] == [False, True, True, True, True]


def test_backtest_volume_membership_rejects_invalid_args():
    from crypto_rsi_scanner import backtest
    idx = pd.date_range("2025-01-01", periods=3, freq="D", tz="UTC")
    frames = {"AAA": pd.DataFrame({"quote_volume": [1.0, 2.0, 3.0]}, index=idx)}

    try:
        backtest.build_volume_membership(frames, top_n=0, window=2)
    except ValueError as e:
        assert "top_n" in str(e)
    else:
        raise AssertionError("top_n=0 should fail")

    try:
        backtest.build_volume_membership(frames, top_n=1, window=0)
    except ValueError as e:
        assert "window" in str(e)
    else:
        raise AssertionError("window=0 should fail")


def test_backtest_main_rejects_invalid_cli_args():
    import contextlib
    import io
    from crypto_rsi_scanner import backtest

    for argv in (
        ["--pit-volume", "--volume-window", "0"],
        ["--top-n", "0"],
        ["--compare-triggers", "--pit"],
    ):
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                backtest.main(argv)
            except SystemExit as e:
                assert e.code == 2
            else:
                raise AssertionError(f"{argv} should fail")


def test_backtest_main_compare_triggers_uses_volume_pit():
    import contextlib
    import io
    from crypto_rsi_scanner import backtest

    calls = {}
    orig_pit_triggers = backtest.run_pit_volume_triggers
    orig_triggers = backtest.run_triggers
    orig_format = backtest.format_trigger_comparison

    def fake_pit_triggers(top_n, days, **kwargs):
        calls["pit"] = {
            "top_n": top_n,
            "days": days,
            "cache_dir": kwargs.get("cache_dir"),
            "refresh_cache": kwargs.get("refresh_cache"),
            "volume_window": kwargs.get("volume_window"),
        }
        return {"cross_into": ([], {}, {}, {}, {}), "confirm": ([], {}, {}, {}, {})}, 2

    def fail_default_triggers(*args, **kwargs):
        raise AssertionError("default trigger path should not run")

    def fake_format(results):
        assert set(results) == {"cross_into", "confirm"}
        return "pit-volume comparison"

    backtest.run_pit_volume_triggers = fake_pit_triggers
    backtest.run_triggers = fail_default_triggers
    backtest.format_trigger_comparison = fake_format
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            backtest.main([
                "--compare-triggers",
                "--pit-volume",
                "--top-n", "7",
                "--days", "30",
                "--volume-window", "3",
                "--no-pit-cache",
            ])
        assert "pit-volume comparison" in out.getvalue()
        assert calls["pit"] == {
            "top_n": 7,
            "days": 30,
            "cache_dir": None,
            "refresh_cache": False,
            "volume_window": 3,
        }
    finally:
        backtest.run_pit_volume_triggers = orig_pit_triggers
        backtest.run_triggers = orig_triggers
        backtest.format_trigger_comparison = orig_format


def test_backtest_fetch_volume_pit_frames_cache_hit_no_sleep_and_closes_session():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import backtest

    cache = Path(tempfile.mkdtemp())
    periods = backtest._START + max(backtest.HORIZONS) + 1
    rows = [
        [
            1735689600000 + i * 86_400_000,
            "1", "2", "0.5", str(100 + i), "10", 0, "15", 0, 0, 0, 0,
        ]
        for i in range(periods)
    ]
    for symbol in ("BTCUSDT", "ETHUSDT"):
        backtest._write_binance_klines_cache(cache, symbol, periods, rows)

    class FakeSession:
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.closed = True

    fake_session = FakeSession()
    sleeps = []
    orig_session = backtest.requests.Session
    orig_pool = backtest.binance_usdt_pool
    orig_sleep = backtest.time.sleep
    backtest.requests.Session = lambda: fake_session
    backtest.binance_usdt_pool = lambda session: ["BTC", "ETH"]
    backtest.time.sleep = lambda seconds: sleeps.append(seconds)
    try:
        frames = backtest._fetch_volume_pit_frames(periods, cache_dir=cache)
        assert set(frames) == {"BTC", "ETH"}
        assert sleeps == []
        assert fake_session.closed is True
    finally:
        backtest.requests.Session = orig_session
        backtest.binance_usdt_pool = orig_pool
        backtest.time.sleep = orig_sleep


def test_backtest_filter_usdt_bases_hygiene():
    from crypto_rsi_scanner import backtest
    syms = [
        {"baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},
        {"baseAsset": "JUP", "quoteAsset": "USDT", "status": "TRADING"},   # real coin, UP suffix
        {"baseAsset": "USDC", "quoteAsset": "USDT", "status": "TRADING"},  # stable
        {"baseAsset": "EUR", "quoteAsset": "USDT", "status": "TRADING"},   # fiat
        {"baseAsset": "WBTC", "quoteAsset": "USDT", "status": "TRADING"},  # wrapped
        {"baseAsset": "OLD", "quoteAsset": "USDT", "status": "BREAK"},     # not trading
        {"baseAsset": "ETH", "quoteAsset": "BTC", "status": "TRADING"},    # wrong quote
        {"baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},   # dup
    ]
    assert backtest._filter_usdt_bases(syms) == ["BTC", "JUP"]


def test_backtest_klines_rows_to_frame_quote_volume():
    from crypto_rsi_scanner import backtest
    # Binance kline array: [open_ms, open, high, low, close, base_vol, close_ms, quote_vol, ...]
    rows = [
        [1735689600000, "1", "2", "0.5", "1.5", "1000", 0, "1500.5", 0, 0, 0, 0],
        [1735776000000, "1.5", "2", "1", "1.8", "2000", 0, "3600.25", 0, 0, 0, 0],
    ]
    df = backtest._klines_rows_to_frame(rows)
    assert list(df["close"]) == [1.5, 1.8]
    assert list(df["high"]) == [2.0, 2.0]
    assert list(df["low"]) == [0.5, 1.0]
    assert list(df["volume"]) == [1000.0, 2000.0]
    assert list(df["quote_volume"]) == [1500.5, 3600.25]
    assert df.index.tz is not None


def test_backtest_binance_klines_cache_roundtrip():
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import backtest
    cache = Path(tempfile.mkdtemp())
    rows = [[1735689600000, "1", "2", "0.5", "1.5", "10", 0, "15", 0, 0, 0, 0]]
    backtest._write_binance_klines_cache(cache, "AAAUSDT", 30, rows)
    # cache hit must not touch the network: session=None would fail otherwise
    df = backtest.fetch_klines("AAAUSDT", 30, session=None, cache_dir=cache)
    assert df is not None and list(df["quote_volume"]) == [15.0]
    assert list(df["high"]) == [2.0]
    assert list(df["low"]) == [0.5]
    # no cache entry + no session -> None (still no network)
    assert backtest.fetch_klines("BBBUSDT", 30, session=None, cache_dir=cache) is None


def test_backtest_pit_history_cache_roundtrip():
    import asyncio
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import backtest

    idx = pd.date_range("2025-01-01", periods=280, freq="D", tz="UTC")
    data = {
        "prices": [[int(ts.timestamp() * 1000), float(i + 1)] for i, ts in enumerate(idx)],
        "market_caps": [[int(ts.timestamp() * 1000), float(1_000_000 + i)] for i, ts in enumerate(idx)],
        "total_volumes": [[int(ts.timestamp() * 1000), float(10_000 + i)] for i, ts in enumerate(idx)],
    }
    cache_dir = Path(tempfile.mkdtemp())
    backtest._write_cg_chart_cache(cache_dir, "bitcoin/test", 365, data)

    path = backtest._cg_chart_cache_path(cache_dir, "bitcoin/test", 365)
    assert path.name == "bitcoin_test-365d.json"
    assert backtest._load_cg_chart_cache(cache_dir, "bitcoin/test", 365)["prices"][0][1] == 1.0

    histories = asyncio.run(backtest._fetch_cg_histories(
        ["bitcoin/test"], 365, cache_dir=cache_dir
    ))
    assert set(histories) == {"bitcoin/test"}
    assert len(histories["bitcoin/test"]) == len(idx)
    assert {"close", "mcap", "volume"}.issubset(histories["bitcoin/test"].columns)


def test_backtest_klines_fixture_loader_and_symbols():
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner.backtest import fixture_symbols, load_klines_fixture

    root = Path(tempfile.mkdtemp()) / "fixture"
    klines = root / "klines"
    klines.mkdir(parents=True)
    (klines / "BTCUSDT.csv").write_text(
        "date,high,low,close,volume,quote_volume\n"
        "2026-01-02T00:00:00Z,102,99,101,1000,101000\n"
        "2026-01-01T00:00:00Z,101,98,100,900,90000\n"
        "2026-01-03T00:00:00Z,104,100,103,1100,113300\n"
    )
    (klines / "ETHUSDT.csv").write_text(
        "date,close,volume\n"
        "2026-01-01T00:00:00Z,10,50\n"
    )

    assert fixture_symbols(root) == ["BTC", "ETH"]
    df = load_klines_fixture("BTCUSDT", 2, root)
    assert df is not None
    assert list(df["close"]) == [101, 103]
    assert list(df["high"]) == [102, 104]
    assert list(df["low"]) == [99, 100]
    assert list(df["quote_volume"]) == [101000, 113300]
    assert str(df.index.tz) == "UTC"


def test_backtest_walk_respects_membership():
    # With a membership mask all-False, no signals and no base days accrue.
    from collections import defaultdict
    from crypto_rsi_scanner import backtest
    rng = np.random.RandomState(2)
    n = 420
    close = pd.Series(
        np.linspace(100, 40, n) + rng.randn(n) * 1.5,
        index=pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
    )
    df = pd.DataFrame({"close": close, "volume": pd.Series(1000.0, index=close.index)})
    sig: list = []
    base: dict = defaultdict(list)
    backtest.walk_coin(df, sig, base, member=np.zeros(n, dtype=bool))
    assert sig == [] and not base


def test_backtest_trigger_modes_differ():
    # An oscillator drives RSI in and out of OB/OS; cross_into and confirm enter
    # on opposite edges of the zone, so their graded outcomes must differ.
    from collections import defaultdict
    from crypto_rsi_scanner import backtest
    n = 500
    close = pd.Series(
        100 + 20 * np.sin(np.arange(n) / 9.0),
        index=pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC"),
    )
    df = pd.DataFrame({"close": close, "volume": pd.Series(1000.0, index=close.index)})
    out = {}
    for trig in ("cross_into", "confirm"):
        sig: list = []
        backtest.walk_coin(df, sig, defaultdict(list), trigger=trig)
        out[trig] = sig
    assert out["cross_into"] and out["confirm"]
    a = sorted(round(s["ret"], 3) for s in out["cross_into"] if s["h"] == 7)
    b = sorted(round(s["ret"], 3) for s in out["confirm"] if s["h"] == 7)
    assert a != b   # different entry timing -> different outcomes


def test_backtest_walk_generates_signals_offline():
    from collections import defaultdict
    from crypto_rsi_scanner import backtest
    rng = np.random.RandomState(1)
    n = 420
    close = pd.Series(
        np.linspace(100, 40, n) + rng.randn(n) * 1.5,  # noisy downtrend
        index=pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
    )
    df = pd.DataFrame({"close": close, "volume": pd.Series(1000.0, index=close.index)})
    signals: list = []
    regime_base: dict = defaultdict(list)
    backtest.walk_coin(df, signals, regime_base)
    assert signals, "expected crossing signals in a long downtrend"
    assert any(s["setup"] == "breakdown_risk" for s in signals)
    assert regime_base
    assert all(s["fav"] in (0, 1) and s["h"] in backtest.HORIZONS for s in signals)


# --- paper-trade scoreboard --------------------------------------------------

def test_paper_is_actionable():
    from crypto_rsi_scanner.paper import _is_actionable
    assert _is_actionable({"setup_type": "dip_buy", "market_aligned": "favorable"})
    assert _is_actionable({"setup_type": "mean_reversion", "market_aligned": "neutral"})
    assert not _is_actionable({"setup_type": "mean_reversion", "market_aligned": "adverse"})
    assert not _is_actionable({"setup_type": "breakdown_risk", "market_aligned": "neutral"})


def test_paper_open_close_pnl_sign():
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import paper, config

    st = Storage(Path(tempfile.mkdtemp()) / "p.db")
    now0 = datetime(2026, 5, 1, tzinfo=timezone.utc)
    signals = [
        {"symbol": "AAA", "coin_id": "aaa", "flag": "OS", "is_new": True, "price": 100.0,
         "setup_type": "dip_buy", "expected_dir": "up", "market_regime": "UPTREND",
         "market_aligned": "favorable", "conviction": 70, "state_json": '{"version":1}'},
        {"symbol": "BBB", "coin_id": "bbb", "flag": "OS", "is_new": True, "price": 100.0,
         "setup_type": "breakdown_risk", "expected_dir": "down", "market_regime": "DOWNTREND",
         "market_aligned": "adverse", "conviction": 40},
    ]
    assert paper.update(st, signals, {}, now=now0) == (2, 0)
    assert paper.update(st, signals, {}, now=now0) == (0, 0)   # one open per coin

    h = config.PAPER_HOLD_DAYS
    idx = pd.date_range(now0, periods=h + 2, freq="D", tz="UTC")
    closes = pd.Series([100.0 + 10.0 * i / h for i in range(len(idx))], index=idx)  # +10% by +h
    later = now0 + timedelta(days=h + 1)
    assert paper.update(st, [], {"aaa": closes, "bbb": closes}, now=later) == (0, 2)

    rows = {r["symbol"]: dict(r) for r in st.closed_paper_trades()}
    assert rows["AAA"]["direction"] == "long" and rows["AAA"]["ret_pct"] > 5   # rose, long wins
    assert rows["AAA"]["state_json"] == '{"version":1}'
    assert rows["BBB"]["direction"] == "short" and rows["BBB"]["ret_pct"] < -5  # rose, short loses
    st.close()


def test_paper_closes_before_opening_same_coin_new_crossing():
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import paper, config

    st = Storage(Path(tempfile.mkdtemp()) / "roll.db")
    now0 = datetime(2026, 5, 1, tzinfo=timezone.utc)
    sig = {"symbol": "AAA", "coin_id": "aaa", "flag": "OS", "is_new": True, "price": 100.0,
           "setup_type": "dip_buy", "expected_dir": "up",
           "market_regime": "UPTREND", "market_aligned": "favorable", "conviction": 70}
    assert paper.update(st, [sig], {}, now=now0) == (1, 0)

    h = config.PAPER_HOLD_DAYS
    idx = pd.date_range(now0, periods=h + 2, freq="D", tz="UTC")
    closes = pd.Series([100.0 + i for i in range(len(idx))], index=idx)
    later = now0 + timedelta(days=h + 1)
    new_sig = {**sig, "price": 120.0, "conviction": 75}
    assert paper.update(st, [new_sig], {"aaa": closes}, now=later) == (1, 1)
    assert len(st.closed_paper_trades()) == 1
    open_rows = [dict(r) for r in st.open_paper_trades()]
    assert len(open_rows) == 1
    assert open_rows[0]["entry_price"] == 120.0
    st.close()


def test_paper_not_closed_before_maturity():
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import paper, config

    st = Storage(Path(tempfile.mkdtemp()) / "p2.db")
    now0 = datetime(2026, 5, 1, tzinfo=timezone.utc)
    sig = [{"symbol": "AAA", "coin_id": "aaa", "flag": "OB", "is_new": True, "price": 50.0,
            "setup_type": "trend_continuation", "expected_dir": "up",
            "market_regime": "UPTREND", "market_aligned": "favorable", "conviction": 60}]
    paper.update(st, sig, {}, now=now0)
    idx = pd.date_range(now0, periods=config.PAPER_HOLD_DAYS + 1, freq="D", tz="UTC")
    closes = pd.Series(55.0, index=idx)
    # only 1 day elapsed -> still open
    early = now0 + timedelta(days=1)
    assert paper.update(st, [], {"aaa": closes}, now=early) == (0, 0)
    assert len(st.open_paper_trades()) == 1
    st.close()


def test_paper_report_empty_and_populated():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner import paper

    st = Storage(Path(tempfile.mkdtemp()) / "p3.db")
    assert "No paper trades yet" in paper.report(st)
    st.conn.execute(
        "INSERT INTO paper_trades (symbol, coin_id, setup_type, market_regime, "
        "market_aligned, state_json, direction, conviction, entry_price, entry_at, hold_days, "
        "exit_price, exit_at, ret_pct, status) VALUES "
        "('AAA','aaa','dip_buy','UPTREND','favorable',"
        "'{\"volatility\":{\"state\":\"high\"},\"breadth\":{\"state\":\"washout\"},"
        "\"relative_strength\":{\"bucket\":\"low\"},\"liquidity\":{\"bucket\":\"mid\"},"
        "\"risk\":{\"falling_knife_score\":80}}',"
        "'long',70,100,'2026-05-01',7,"
        "110,'2026-05-08',10.0,'closed')"
    )
    st.conn.execute(
        "INSERT INTO paper_trades (symbol, coin_id, setup_type, market_regime, "
        "market_aligned, direction, conviction, entry_price, entry_at, hold_days, "
        "exit_price, exit_at, ret_pct, status) VALUES "
        "('BBB','bbb','breakdown_risk','DOWNTREND','adverse','short',40,100,'2026-05-01',7,"
        "108,'2026-05-08',-8.0,'closed')"
    )
    st.conn.commit()
    out = paper.report(st)
    assert "PAPER-TRADE SCOREBOARD" in out
    assert "actionable" in out and "control" in out
    assert "By conviction bucket" in out
    cohorts = paper.report(st, cohorts=True)
    assert "By state cohort" in cohorts
    assert "volatility" in cohorts and "high" in cohorts
    assert "falling-knife" in cohorts
    data = paper.summary(st)
    assert data["closed_count"] == 2
    assert data["books"]["actionable"]["n"] == 1
    assert data["by_conviction_bucket"]["65-79"]["n"] == 1
    assert data["by_conviction_bucket"]["0-49"]["n"] == 1
    assert data["by_state"]["volatility"]["high"]["n"] == 1
    st.close()


def test_refresh_paper_closes_without_scan_or_alerts():
    import contextlib
    import io
    from crypto_rsi_scanner import scanner

    calls = {}

    class FakeStorage:
        def __init__(self, path):
            self.path = path
            calls["storage_path"] = path

        def open_paper_coin_ids(self):
            return ["aaa", "bbb"]

        def close(self):
            calls["closed_storage"] = True

    async def fake_fetch(ids):
        calls["fetch_ids"] = list(ids)
        return {"aaa": pd.Series([1.0]), "bbb": pd.Series([2.0])}

    def fake_update(storage, signals, closes_map):
        calls["update"] = (storage, list(signals), sorted(closes_map))
        return 0, 2

    def fake_report(storage, cohorts=False):
        calls["cohorts"] = cohorts
        return "paper report"

    orig_storage = scanner.Storage
    orig_fetch = scanner._fetch_extra_daily_closes
    orig_update = scanner.paper.update
    orig_report = scanner.paper.report
    scanner.Storage = FakeStorage
    scanner._fetch_extra_daily_closes = fake_fetch
    scanner.paper.update = fake_update
    scanner.paper.report = fake_report
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.refresh_paper(cohorts=True)
        assert "closed 2 trade(s)" in out.getvalue()
        assert "paper report" in out.getvalue()
        assert calls["fetch_ids"] == ["aaa", "bbb"]
        assert calls["update"][1] == []
        assert calls["update"][2] == ["aaa", "bbb"]
        assert calls["cohorts"] is True
        assert calls["closed_storage"] is True
    finally:
        scanner.Storage = orig_storage
        scanner._fetch_extra_daily_closes = orig_fetch
        scanner.paper.update = orig_update
        scanner.paper.report = orig_report


# --- regression: NaN enrichment from the DataFrame self-tune path -------------

def test_tg_card_tolerates_nan_enrichment():
    # _apply_live_edge_adjustments adds track_record/conviction_base columns; rows
    # without a value arrive here as NaN (float). _tg_card must not crash/leak it.
    s = _sample_signal(setup_type="mean_reversion", expected_dir="up",
                       track_record=float("nan"), conviction_base=float("nan"))
    out = formatting._tg_card(s)            # must not raise
    assert "nan" not in out.lower()


def test_live_edge_adjust_render_no_nan():
    import pandas as pd
    from crypto_rsi_scanner import scanner, outcomes

    class _FakeStore:
        def outcomes_joined(self):
            return [{"x": 1}]                # non-empty so the adjuster proceeds

    orig = outcomes.track_records
    outcomes.track_records = lambda rows, h: {"dip_buy": {"n": 10, "hit": 7, "med_ret": 2.0}}
    try:
        def row(sym, setup):
            return {"symbol": sym, "coin_id": sym.lower(), "flag": "OS",
                    "severity": "ALERT", "conviction": 55, "setup_type": setup,
                    "expected_dir": "up", "regime": "RANGE", "regime_note": "x",
                    "market_regime": "UPTREND", "market_aligned": "favorable",
                    "rsi_daily": 28.0, "rsi_4h": None, "rsi_weekly": None,
                    "rsi_z": 0.0, "rsi_delta": 0.0, "volume_ratio": 1.0,
                    "btc_corr": 0.0, "divergence": None, "price": 100.0}
        # AAA has a track record (dip_buy); ZZZ does NOT (mean_reversion) -> NaN row
        df = pd.DataFrame([row("AAA", "dip_buy"), row("ZZZ", "mean_reversion")])
        df = scanner._apply_live_edge_adjustments(df, _FakeStore())
        _, signals = scanner.build_message(df, {})
        for s in signals:
            card = formatting._tg_card(s)    # must not raise for the NaN-row coin
            assert "nan" not in card.lower(), f"NaN leaked for {s['symbol']}"
    finally:
        outcomes.track_records = orig


def test_route_notifications_only_marks_successful_sends():
    from crypto_rsi_scanner import scanner

    class Store:
        def __init__(self):
            self.alerted = []
            self.digest_marked = False
        def active_subscribers(self):
            return ["1"]
        def is_on_cooldown(self, symbol, flag, cooldown_hours):
            return False
        def mark_alerted(self, symbol, flag):
            self.alerted.append((symbol, flag))
        def digest_due(self, interval_hours):
            return True
        def mark_digest_sent(self):
            self.digest_marked = True

    signals = [
        {"symbol": "AAA", "flag": "OB", "tier": "INSTANT", "is_new": True, "conviction": 90},
        {"symbol": "BBB", "flag": "PRE_OS", "tier": "DIGEST", "is_new": True, "conviction": 35},
    ]
    orig = scanner.notify_all
    try:
        store = Store()
        scanner.notify_all = lambda *args, **kwargs: []
        stats = scanner._route_notifications(signals, store, dry_run=False)
        assert stats["instant_sent"] is False and stats["digest_sent"] is False
        assert store.alerted == []
        assert store.digest_marked is False

        store = Store()
        scanner.notify_all = lambda *args, **kwargs: ["Telegram"]
        stats = scanner._route_notifications(signals, store, dry_run=False)
        assert stats["instant_sent"] is True and stats["digest_sent"] is True
        assert store.alerted == [("AAA", "OB")]
        assert store.digest_marked is True
    finally:
        scanner.notify_all = orig


def test_telegram_send_chunks_long_messages():
    from crypto_rsi_scanner import notifications, config

    class Response:
        def raise_for_status(self):
            return None

    calls = []
    orig_post = notifications.requests.post
    orig_token = config.TELEGRAM_BOT_TOKEN
    orig_chat_ids = config.TELEGRAM_CHAT_IDS
    notifications.requests.post = lambda url, json, timeout: calls.append(json["text"]) or Response()
    config.TELEGRAM_BOT_TOKEN = "token"
    config.TELEGRAM_CHAT_IDS = ["1"]
    try:
        text = ("signal line\n\n" * 700).strip()
        assert len(text) > 4096
        assert notifications.send_telegram(text, parse_mode="HTML") is True
        assert len(calls) > 1
        assert all(len(body) <= 4096 for body in calls)
        assert not any("…" in body for body in calls)
        assert "signal line" in calls[-1]
    finally:
        notifications.requests.post = orig_post
        config.TELEGRAM_BOT_TOKEN = orig_token
        config.TELEGRAM_CHAT_IDS = orig_chat_ids


def test_telegram_structured_send_tracks_recipients_chunks_and_bool_compat():
    from crypto_rsi_scanner import notifications, config

    class Response:
        def __init__(self, fail=False):
            self.fail = fail

        def raise_for_status(self):
            if self.fail:
                raise RuntimeError("bad token=SECRET123")

    calls = []
    orig_post = notifications.requests.post
    orig_token = config.TELEGRAM_BOT_TOKEN
    orig_chat_ids = config.TELEGRAM_CHAT_IDS

    def fake_post(url, json, timeout):
        calls.append((url, dict(json), timeout))
        return Response(fail=json["chat_id"] == "bad")

    notifications.requests.post = fake_post
    config.TELEGRAM_BOT_TOKEN = "SECRET123"
    config.TELEGRAM_CHAT_IDS = ["good", "bad"]
    try:
        result = notifications.send_telegram_structured("hello", parse_mode="HTML")
        assert result.attempted is True
        assert result.success is False
        assert result.recipient_count == 2
        assert result.delivered_count == 1
        assert result.failed_count == 1
        assert result.chunk_count == 1
        assert result.delivered_chunks == 1
        assert result.failed_chunks == 1
        assert "SECRET123" not in str(result.error_message_safe)
        assert "SECRET123" not in str(result.channel_summary)
        assert notifications.send_telegram("legacy bool", parse_mode="HTML") is True
        assert len(calls) >= 4
        assert {call[2] for call in calls} == {notifications.TELEGRAM_SEND_TIMEOUT_SECONDS}
    finally:
        notifications.requests.post = orig_post
        config.TELEGRAM_BOT_TOKEN = orig_token
        config.TELEGRAM_CHAT_IDS = orig_chat_ids


def test_telegram_structured_send_counts_chunked_success():
    from crypto_rsi_scanner import notifications, config

    class Response:
        def raise_for_status(self):
            return None

    calls = []
    orig_post = notifications.requests.post
    orig_token = config.TELEGRAM_BOT_TOKEN
    orig_chat_ids = config.TELEGRAM_CHAT_IDS
    notifications.requests.post = lambda url, json, timeout: calls.append(json["text"]) or Response()
    config.TELEGRAM_BOT_TOKEN = "token"
    config.TELEGRAM_CHAT_IDS = ["1"]
    try:
        text = ("alpha\n\n" * 900).strip()
        result = notifications.send_telegram_structured(text, parse_mode="HTML")
        assert result.success is True
        assert result.delivered_count == 1
        assert result.failed_count == 0
        assert result.chunk_count == len(calls)
        assert result.delivered_chunks == result.chunk_count
        assert result.failed_chunks == 0
    finally:
        notifications.requests.post = orig_post
        config.TELEGRAM_BOT_TOKEN = orig_token
        config.TELEGRAM_CHAT_IDS = orig_chat_ids


def test_scan_staleness_alert_dedup_and_recovery():
    from datetime import datetime, timedelta, timezone
    from crypto_rsi_scanner import telegram, heartbeat, config

    sent = []
    orig_alert = heartbeat.alert_stale_scan
    orig_int = config.STALE_CHECK_INTERVAL_SEC
    heartbeat.alert_stale_scan = lambda last, hrs, storage=None: sent.append(hrs)
    config.STALE_CHECK_INTERVAL_SEC = 0           # disable throttle for the test
    try:
        now = datetime(2026, 6, 8, tzinfo=timezone.utc)

        class Store:
            def __init__(self, dt):
                self.dt = dt
            def last_scan_at(self):
                return self.dt

        state: dict = {}
        telegram._check_scan_staleness(Store(now - timedelta(hours=2)), state, now=now)
        assert sent == []                          # fresh -> no alert
        telegram._check_scan_staleness(Store(now - timedelta(hours=40)), state, now=now)
        assert len(sent) == 1                      # stale -> one alert
        telegram._check_scan_staleness(Store(now - timedelta(hours=41)), state, now=now)
        assert len(sent) == 1                      # still stale -> no repeat (dedup)
        telegram._check_scan_staleness(Store(now - timedelta(hours=1)), state, now=now)
        telegram._check_scan_staleness(Store(now - timedelta(hours=40)), state, now=now)
        assert len(sent) == 2                      # recovered then stale again -> re-alerts
        # no scan history yet -> never alerts
        telegram._check_scan_staleness(Store(None), {}, now=now)
        assert len(sent) == 2
    finally:
        heartbeat.alert_stale_scan = orig_alert
        config.STALE_CHECK_INTERVAL_SEC = orig_int


def test_scan_status_lifecycle_and_report():
    import json
    from datetime import datetime, timedelta, timezone

    from crypto_rsi_scanner import config, status_report, telegram

    st = _fresh_storage()
    orig_stale = config.STALE_SCAN_HOURS
    config.STALE_SCAN_HOURS = 36
    try:
        st.mark_scan_started(top_n=12)
        assert st.scan_status()["state"] == "running"

        st.mark_scan_success(
            top_n=12,
            requested=15,
            fetched=14,
            analyzed=12,
            coin_count=12,
            flagged_count=3,
            ob_count=2,
            os_count=1,
            instant_count=1,
            digest_count=2,
            matured_outcomes=4,
            paper_opened=1,
            paper_closed=0,
        )
        status = st.scan_status()
        assert status["state"] == "success"
        assert st.last_successful_scan_at() is not None
        telegram.save_latest_snapshot(st, [{"symbol": "AAA", "flag": "OB"}])
        st.subscribe("111", "alice")

        out = status_report.format_status(st)
        assert "health: OK" in out
        assert "fetch: requested 15, fetched 14, analyzed 12" in out
        assert "signals: scanned 12, flagged 3 (OB 2, OS 1)" in out
        assert "bot: 1 subscriber(s), 1 current snapshot signal(s)" in out

        old = datetime.now(timezone.utc) - timedelta(hours=40)
        status["last_success_at"] = old.isoformat()
        st.set_meta("scan_status", json.dumps(status))
        assert "health: STALE" in status_report.format_status(st, now=datetime.now(timezone.utc))
    finally:
        config.STALE_SCAN_HOURS = orig_stale
        st.close()


def test_scan_status_failure_and_bot_health_escapes():
    from crypto_rsi_scanner import telegram

    st = _fresh_storage()
    try:
        st.mark_scan_started(top_n=10)
        st.mark_scan_failure("bad <network> & token", requested=10, fetched=0, analyzed=0)
        plain = telegram._cmd_health(st)
        assert "RSI SCANNER STATUS" in plain
        assert "health: FAILED" in plain
        assert "bad &lt;network&gt; &amp; token" in plain
        assert "<network>" not in plain
    finally:
        st.close()


def test_sqlite_backup_api_integrity_and_retention():
    import sqlite3
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    from crypto_rsi_scanner.backups import backup_database

    root = Path(tempfile.mkdtemp())
    src = root / "source.db"
    backup_dir = root / "backups"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO sample (value) VALUES ('ok')")
    conn.commit()
    conn.close()

    result = backup_database(
        src,
        backup_dir,
        keep=2,
        now=datetime(2026, 6, 8, 1, 2, 3, tzinfo=timezone.utc),
    )
    assert result.path.exists()
    assert result.quick_check == "ok"
    copied = sqlite3.connect(result.path)
    try:
        assert copied.execute("SELECT value FROM sample").fetchone()[0] == "ok"
    finally:
        copied.close()

    backup_database(src, backup_dir, keep=2, now=datetime(2026, 6, 8, 1, 2, 4, tzinfo=timezone.utc))
    third = backup_database(src, backup_dir, keep=2, now=datetime(2026, 6, 8, 1, 2, 5, tzinfo=timezone.utc))
    backups = sorted(backup_dir.glob("source-*.db"))
    assert len(backups) == 2
    assert backups[-1] == third.path
    assert not result.path.exists()


def test_sqlite_restore_drill_checks_schema_counts():
    import sqlite3
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    from crypto_rsi_scanner.backups import backup_database, format_restore_result, verify_restore

    root = Path(tempfile.mkdtemp())
    src = root / "source.db"
    backup_dir = root / "backups"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE scans (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE signals (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("CREATE TABLE paper_trades (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO scans DEFAULT VALUES")
    conn.execute("INSERT INTO meta (key, value) VALUES ('k', 'v')")
    conn.commit()
    conn.close()

    backup = backup_database(
        src,
        backup_dir,
        now=datetime(2026, 6, 8, 2, 0, 0, tzinfo=timezone.utc),
    )
    result = verify_restore(
        backup.path,
        expected_tables=("scans", "signals", "meta", "paper_trades"),
    )
    assert result.quick_check == "ok"
    assert result.table_counts["scans"] == 1
    assert result.table_counts["meta"] == 1
    assert "SQLite restore drill complete" in format_restore_result(result)


def test_backup_freshness_status_report():
    import sqlite3
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    from crypto_rsi_scanner import config, status_report
    from crypto_rsi_scanner.backups import backup_database

    root = Path(tempfile.mkdtemp())
    src = root / "rsi_scanner.db"
    backup_dir = root / "backups"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    st = _fresh_storage()
    orig_db = config.DB_PATH
    orig_dir = config.BACKUP_DIR
    orig_keep = config.BACKUP_KEEP
    orig_stale = config.BACKUP_STALE_HOURS
    orig_logs = config.LOG_FILES
    config.DB_PATH = src
    config.BACKUP_DIR = backup_dir
    config.BACKUP_KEEP = 2
    config.BACKUP_STALE_HOURS = 24
    config.LOG_FILES = []
    try:
        created = datetime(2026, 6, 8, 1, 0, 0, tzinfo=timezone.utc)
        backup_database(src, backup_dir, keep=2, now=created)

        fresh = status_report.format_status(st, now=created + timedelta(hours=2))
        assert "backup: OK" in fresh
        assert "rsi_scanner-20260608T010000Z.db" in fresh
        assert "2.0h ago" in fresh
        assert "1/2 retained" in fresh

        stale = status_report.format_status(st, now=created + timedelta(hours=25))
        assert "backup: STALE" in stale

        config.BACKUP_DIR = root / "empty"
        missing = status_report.format_status(st, now=created + timedelta(hours=2))
        assert "backup: MISSING" in missing
        assert "run main.py --backup-db" in missing
    finally:
        config.DB_PATH = orig_db
        config.BACKUP_DIR = orig_dir
        config.BACKUP_KEEP = orig_keep
        config.BACKUP_STALE_HOURS = orig_stale
        config.LOG_FILES = orig_logs
        st.close()


def test_log_rotation_copytruncate_and_retention():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    from crypto_rsi_scanner.ops import log_file_status, rotate_logs

    root = Path(tempfile.mkdtemp())
    log = root / "bot.log"
    first_time = datetime(2026, 6, 8, 1, 0, 0, tzinfo=timezone.utc)
    second_time = datetime(2026, 6, 8, 1, 0, 1, tzinfo=timezone.utc)

    log.write_text("first rotation\n", encoding="utf-8")
    first = rotate_logs([log], max_bytes=3, keep=1, now=first_time)[0]
    assert first.reason == "rotated"
    assert first.rotated_to is not None
    assert first.rotated_to.read_text(encoding="utf-8") == "first rotation\n"
    assert log.read_text(encoding="utf-8") == ""

    log.write_text("second rotation\n", encoding="utf-8")
    second = rotate_logs([log], max_bytes=3, keep=1, now=second_time)[0]
    assert second.reason == "rotated"
    assert second.rotated_to is not None
    assert second.rotated_to.read_text(encoding="utf-8") == "second rotation\n"
    assert not first.rotated_to.exists()
    assert len(list(root.glob("bot.log.*"))) == 1
    assert log.read_text(encoding="utf-8") == ""

    status = log_file_status([log], max_bytes=3)[0]
    assert status.exists is True
    assert status.size_bytes == 0
    assert status.rotation_count == 1


def test_launchd_status_parser_and_formatter():
    from crypto_rsi_scanner.ops import _parse_launchctl_print, format_launchd_status

    text = """
gui/501/com.nasrenkaraf.rsibot = {
    path = /Users/nasrenkaraf/Library/LaunchAgents/com.nasrenkaraf.rsibot.plist
    state = running
    stdout path = /Users/nasrenkaraf/crypto-rsi-scanner/bot.log
    stderr path = /Users/nasrenkaraf/crypto-rsi-scanner/bot.log
    runs = 8
    pid = 73052
    last exit code = 0
}
"""
    status = _parse_launchctl_print("com.nasrenkaraf.rsibot", "gui/501", text)
    assert status.loaded is True
    assert status.state == "running"
    assert status.pid == 73052
    assert status.runs == 8
    assert status.last_exit_code == 0
    assert status.stdout_path.endswith("bot.log")

    out = format_launchd_status([status])
    assert "com.nasrenkaraf.rsibot: running, pid 73052, runs 8, last exit 0" in out
    assert "stdout: /Users/nasrenkaraf/crypto-rsi-scanner/bot.log" in out


def test_maintenance_agent_plist_contents():
    from pathlib import Path
    from crypto_rsi_scanner.ops import maintenance_agent_plist

    plist = maintenance_agent_plist(
        label="com.example.maint",
        python_path=Path("/repo/.venv/bin/python"),
        main_path=Path("/repo/main.py"),
        working_dir=Path("/repo"),
        log_path=Path("/repo/maintenance.log"),
        hour=3,
        minute=45,
    )
    assert plist["Label"] == "com.example.maint"
    assert plist["ProgramArguments"] == ["/repo/.venv/bin/python", "/repo/main.py", "--maintenance"]
    assert plist["WorkingDirectory"] == "/repo"
    assert plist["StandardOutPath"] == "/repo/maintenance.log"
    assert plist["StartCalendarInterval"] == {"Hour": 3, "Minute": 45}
    assert plist["RunAtLoad"] is False


def test_coingecko_client_fixture_mode():
    import asyncio
    import json
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import config
    from crypto_rsi_scanner.client import CoinGeckoClient

    root = Path(tempfile.mkdtemp())
    chart_dir = root / "market_chart"
    chart_dir.mkdir()
    (root / "top_markets.json").write_text(json.dumps([
        {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
        {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
    ]))
    (chart_dir / "bitcoin.json").write_text(json.dumps({
        "prices": [[1, 100.0]],
        "total_volumes": [[1, 1000.0]],
    }))

    orig = config.FIXTURE_DIR
    config.FIXTURE_DIR = root
    try:
        async def _run():
            async with CoinGeckoClient() as client:
                markets = await client.get_top_markets(1)
                chart = await client.get_market_chart("bitcoin", 250)
                return markets, chart
        markets, chart = asyncio.run(_run())
        assert [m["id"] for m in markets] == ["bitcoin"]
        assert chart["prices"][0][1] == 100.0
    finally:
        config.FIXTURE_DIR = orig


def test_storage_wal_and_busy_timeout():
    # The scan and the always-on listener share one DB file; WAL + busy_timeout
    # let them read/write concurrently without "database is locked".
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.storage import Storage
    st = Storage(Path(tempfile.mkdtemp()) / "wal.db")
    try:
        assert str(st.conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        assert st.conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 1000
    finally:
        st.close()












































def test_normalize_export_timestamps_clamps_future_mtimes():
    import os
    from scripts import normalize_export_timestamps

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        future = root / "future.txt"
        future.write_text("future\n", encoding="utf-8")
        old = root / "old.txt"
        old.write_text("old\n", encoding="utf-8")
        now_ts = 1_800_000_000.0
        os.utime(future, (now_ts + 500, now_ts + 500))
        os.utime(old, (now_ts - 500, now_ts - 500))
        changed = normalize_export_timestamps.normalize_path_timestamps(root, now_ts=now_ts)
        assert changed == 1
        assert future.stat().st_mtime <= now_ts
        assert old.stat().st_mtime == now_ts - 500








def _test_watchlist_entry(*, state: str, symbol: str, coin_id: str):
    from crypto_rsi_scanner import event_watchlist

    high_priority = state == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value
    return event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key=f"cluster|{coin_id}|proxy_attention",
        cluster_id="cluster",
        event_id="event",
        coin_id=coin_id,
        symbol=symbol,
        relationship_type="proxy_exposure",
        external_asset="SpaceX",
        event_time="2026-06-16T00:00:00+00:00",
        state=state,
        previous_state=None,
        first_seen_at="2026-06-15T00:00:00+00:00",
        last_seen_at="2026-06-15T00:00:00+00:00",
        source_count=1,
        highest_score=80,
        latest_score=80,
        latest_tier="HIGH_PRIORITY_WATCH" if state == "HIGH_PRIORITY" else "WATCHLIST",
        latest_event_name="SpaceX pre-IPO exposure",
        latest_source="fixture",
        latest_playbook_type="proxy_attention",
        latest_effective_playbook_type="proxy_attention",
        latest_market_snapshot={},
        latest_score_components={
            "cluster_confidence": 70,
            "impact_path_type": "proxy_exposure",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_instrument",
            "evidence_quality_score": 78,
            "source_class": "crypto_native",
            "evidence_specificity": "asset_and_catalyst",
            "market_confirmation_score": 88 if high_priority else 70,
            "market_confirmation_level": "strong" if high_priority else "confirmed",
            "opportunity_score_final": 92 if high_priority else 82,
            "opportunity_level": "high_priority" if high_priority else "watchlist",
            "opportunity_verdict_reasons": ["fixture_watchlist_quality_context"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "already_watchlisted",
            "manual_verification_items": ["verify source, catalyst timing, and liquidity"],
            "upgrade_requirements": [],
            "downgrade_warnings": [],
        },
    )


def _notify_artifact_context(base, namespace):
    from types import SimpleNamespace
    from pathlib import Path

    base = Path(base)
    return SimpleNamespace(
        profile=namespace,
        run_mode="notification_burn_in",
        artifact_namespace=namespace,
        base_dir=base,
        namespace_dir=base / namespace,
    )


class _NotifyFakeStorage:
    def __init__(self):
        self.meta = {}

    def get_meta(self, key):
        return self.meta.get(key)

    def set_meta(self, key, value):
        self.meta[key] = value


def _notify_route_decision(symbol, lane, route):
    from crypto_rsi_scanner import event_alpha_router, event_watchlist

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key=f"{symbol}|proxy",
        cluster_id=f"{symbol}|cluster",
        event_id=f"evt-{symbol}",
        coin_id=symbol.lower(),
        symbol=symbol,
        relationship_type="proxy_attention",
        external_asset="SpaceX",
        event_time="2026-06-20T13:30:00+00:00",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        previous_state="WATCHLIST",
        first_seen_at="2026-06-19T09:00:00+00:00",
        last_seen_at="2026-06-19T11:00:00+00:00",
    )
    return event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=route,
        alertable=True,
        reason="state escalation",
        lane=lane,
    )


def _notify_suppressed_decision(
    symbol,
    *,
    key_suffix="proxy",
    playbook="market_anomaly_unknown",
    relationship="ambiguous",
    llm_role=None,
    score=35,
    source="fixture_source",
    reason="raw/store-only evidence, no alertable watchlist state",
):
    from crypto_rsi_scanner import event_alpha_router, event_watchlist

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key=f"{symbol}|{key_suffix}",
        cluster_id=f"{symbol}|cluster",
        event_id=f"evt-{symbol}",
        coin_id=symbol.lower(),
        symbol=symbol,
        relationship_type=relationship,
        external_asset="SpaceX" if playbook != "source_noise_control" else None,
        event_time="2026-06-20T13:30:00+00:00" if playbook != "source_noise_control" else None,
        state=event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        previous_state=None,
        first_seen_at="2026-06-19T09:00:00+00:00",
        last_seen_at="2026-06-19T11:00:00+00:00",
        source_count=1,
        highest_score=score,
        latest_score=score,
        latest_tier="STORE_ONLY",
        latest_event_name=f"{symbol} exploratory catalyst",
        latest_source=source,
        latest_playbook_type=playbook,
        latest_effective_playbook_type=playbook,
        latest_llm_asset_role=llm_role,
        latest_llm_confidence=0.82 if llm_role else None,
        latest_market_snapshot={
            "price": 1.23,
            "return_24h": 0.42,
            "return_72h": 1.404,
            "volume_mcap": 0.33,
            "volume_zscore_24h": 3.4,
        },
        latest_score_components={
            "classifier": 48,
            "market_move_volume": 65,
            "source_quality": 55,
            "cluster_confidence": 50,
            "novelty_freshness": 45,
        },
        suppressed_reason=reason,
        should_alert=False,
    )
    return event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.STORE_ONLY,
        alertable=False,
        reason=reason,
        lane=event_alpha_router.EventAlphaRouteLane.LOCAL_ONLY,
    )








































def _research_review_decision(symbol="DOGE", *, score=66, level="exploratory", playbook="meme_attention"):
    decision = _notify_suppressed_decision(
        symbol,
        playbook=playbook,
        relationship="proxy_attention",
        score=score,
        reason="missing independent source confirmation",
    )
    decision.entry.latest_score_components.update({
        "core_opportunity_id": f"agg:{symbol.lower()}-research-review",
        "opportunity_level": level,
        "opportunity_score_final": score,
        "impact_path_type": playbook,
        "candidate_role": "candidate_asset",
        "market_confirmation_score": 70,
        "source_quality": 58,
        "why_not_watchlist": "missing independent source confirmation",
        "upgrade_requirements": ["find independent catalyst evidence", "verify liquidity and organic volume"],
    })
    return decision






































































































































































































































def _canonical_core_fixture_rows() -> list[dict[str, object]]:
    from crypto_rsi_scanner import event_alpha_router, event_watchlist

    base = {
        "profile": "market_refresh_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "market_refresh_smoke",
        "row_type": "event_impact_hypothesis",
        "source_class": "validated_source",
        "evidence_specificity": "specific",
    }
    return [
        {
            **base,
            "hypothesis_id": "hyp-velvet-core",
            "incident_id": "incident-spacex",
            "canonical_incident_name": "SpaceX pre-IPO exposure",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "candidate_role": "proxy_venue",
            "impact_category": "tokenized_stock_venue",
            "impact_path_type": "venue_value_capture",
            "opportunity_level": "high_priority",
            "opportunity_score_final": 92,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            "market_refresh_attempted": True,
            "market_refresh_success": True,
            "market_context_freshness_status": "fresh",
            "market_context_source": "market_refresh",
            "market_context_age_hours": 0.5,
            "market_context_freshness_cap_applied": False,
            "market_confirmation_after": 88,
            "evidence_acquisition_attempted": True,
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_quality_after": 91,
            "evidence_quotes": ["Velvet offers SpaceX exposure"],
        },
        {
            **base,
            "hypothesis_id": "hyp-velvet-stale-support",
            "incident_id": "incident-spacex",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "candidate_role": "proxy_venue",
            "impact_category": "rwa_preipo_proxy",
            "impact_path_type": "rwa_preipo_proxy",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 70,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "market_context_freshness_status": "stale",
            "market_context_freshness_cap_applied": True,
            "why_not_watchlist": ["market_context_stale_capped"],
            "evidence_quotes": ["SpaceX pre-IPO market mention"],
        },
        {
            **base,
            "hypothesis_id": "hyp-aave-core",
            "incident_id": "incident-kraken-aave",
            "canonical_incident_name": "Kraken strategic Aave stake",
            "symbol": "AAVE",
            "coin_id": "aave",
            "validated_symbol": "AAVE",
            "validated_coin_id": "aave",
            "candidate_role": "direct_beneficiary",
            "impact_category": "strategic_investment",
            "impact_path_type": "strategic_investment",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 76,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "evidence_quotes": ["Kraken acquired a strategic stake in Aave"],
        },
        {
            **base,
            "hypothesis_id": "hyp-rune-core",
            "incident_id": "incident-thorchain-exploit",
            "canonical_incident_name": "THORChain exploit and trading restart",
            "symbol": "RUNE",
            "coin_id": "thorchain",
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "candidate_role": "direct_beneficiary",
            "impact_category": "security_incident",
            "impact_path_type": "exploit_security_event",
            "opportunity_level": "watchlist",
            "opportunity_score_final": 81,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.WATCHLIST.value,
            "market_refresh_attempted": True,
            "market_refresh_success": True,
            "market_confirmation_after": 73,
            "evidence_quotes": ["THORChain resumed trading after exploit response"],
        },
        {
            **base,
            "hypothesis_id": "hyp-meme-core",
            "incident_id": "incident-memecore",
            "symbol": "MEME",
            "coin_id": "memecore",
            "validated_symbol": "MEME",
            "validated_coin_id": "memecore",
            "candidate_role": "mentioned_asset",
            "impact_category": "market_anomaly",
            "impact_path_type": "insufficient_data",
            "opportunity_level": "local_only",
            "opportunity_score_final": 42,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.LOCAL_REPORT.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "why_local_only": ["missing_direct_impact_path"],
        },
    ]
















































































































































































def test_cli_dispatch_extracts_representative_routes_without_side_effects():
    from crypto_rsi_scanner import scanner as scanner_module
    from crypto_rsi_scanner.cli.dispatch import dispatch_args
    from crypto_rsi_scanner.cli.parser import build_parser

    parser = build_parser()
    calls = []
    old_coinalyze = scanner_module.event_alpha_coinalyze_preflight_report
    old_run = scanner_module.run
    try:
        scanner_module.event_alpha_coinalyze_preflight_report = lambda **kwargs: calls.append(("coinalyze", kwargs))
        scanner_module.run = lambda **kwargs: calls.append(("run", kwargs))
        dispatch_args(parser.parse_args(["--event-alpha-coinalyze-preflight", "--event-alpha-profile", "fixture"]))
        dispatch_args(parser.parse_args(["--dry-run", "--top-n", "3"]))
    finally:
        scanner_module.event_alpha_coinalyze_preflight_report = old_coinalyze
        scanner_module.run = old_run

    assert calls[0] == (
        "coinalyze",
        {
            "verbose": False,
            "profile_name": "fixture",
            "artifact_namespace": None,
            "smoke_mode": False,
            "allow_live_preflight": False,
        },
    )
    assert calls[1] == ("run", {"top_n": 3, "dry_run": True, "verbose": False})


def test_github_actions_are_safe_fixture_verification_only():
    root = Path(__file__).resolve().parent.parent
    verify = root / ".github" / "workflows" / "verify.yml"
    smoke = root / ".github" / "workflows" / "event-alpha-smoke.yml"
    assert verify.exists()
    assert smoke.exists()
    text = (verify.read_text(encoding="utf-8") + "\n" + smoke.read_text(encoding="utf-8")).casefold()
    forbidden = (
        "allow_live",
        "allow-live",
        "rsi_event_alerts_enabled=1",
        "event-alert-send",
        "event-alpha-cycle-send",
        "event-alpha-telegram-send-one-cycle",
        "telegram_bot_token",
        "coinalyze_api_key",
    )
    for item in forbidden:
        assert item not in text
    assert "make verify python=python3" in text
    assert "event-alpha-integrated-radar-smoke" in text


def test_refactor_baseline_generation_writes_reports_without_behavior_invocation():
    from crypto_rsi_scanner import refactor_baseline

    root = Path(__file__).resolve().parent.parent
    with TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "research"
        paths = refactor_baseline.write_refactor_baseline(root=root, out_dir=out_dir)
        assert paths["json"].exists()
        assert paths["markdown"].exists()
        payload = json.loads(paths["json"].read_text(encoding="utf-8"))
        markdown = paths["markdown"].read_text(encoding="utf-8")

    assert payload["schema_version"] == "refactor_baseline_v1"
    assert payload["static_inventory_only"] is True
    assert payload["behavior_changing_code_invoked"] is False
    assert payload["live_provider_calls_allowed"] is False
    assert payload["telegram_sends"] == 0
    assert payload["trades_created"] == 0
    assert payload["paper_trades_created"] == 0
    assert payload["normal_rsi_signal_rows_written"] == 0
    assert payload["triggered_fade_created"] == 0
    assert "Behavior Freeze Contract" in markdown
    assert "Refactor Success Gates" in markdown


def test_refactor_baseline_json_contains_file_counts_and_inventory():
    from crypto_rsi_scanner import refactor_baseline

    root = Path(__file__).resolve().parent.parent
    payload = refactor_baseline.build_refactor_baseline(root=root)
    counts = payload["line_counts"]
    assert counts["crypto_rsi_scanner/scanner.py"] > 4000
    assert counts["tests/test_indicators.py"] > 2000
    assert counts["crypto_rsi_scanner/event_alpha_artifact_doctor.py"] > 1500
    assert payload["top_level_event_module_count"] == len(payload["top_level_event_modules"])
    assert payload["top_level_event_module_count"] > 0
    assert "crypto_rsi_scanner/event_alpha/artifacts/schema_v1.py" in payload["event_alpha_package_files"]
    assert "crypto_rsi_scanner/cli/parser.py" in payload["cli_package_files"]
    assert "tests/test_indicators.py" in payload["tests_package_files"]
    assert ".github/workflows/verify.yml" in payload["github_actions_workflows"]
    assert "event-alpha-integrated-radar-smoke" in payload["makefile_event_targets"]
    assert payload["namespace_inventory"]["base_dir"] == "event_fade_cache"


def test_refactor_baseline_make_target_is_static_and_no_live_runtime_path():
    root = Path(__file__).resolve().parent.parent
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    module_text = (root / "crypto_rsi_scanner" / "refactor_baseline.py").read_text(encoding="utf-8").casefold()
    assert "refactor-baseline:" in makefile
    assert "$(python) -m crypto_rsi_scanner.refactor_baseline" in makefile.casefold()
    forbidden = (
        "urlopen",
        "requests.",
        "aiohttp",
        "from crypto_rsi_scanner.scanner import",
        "import crypto_rsi_scanner.scanner",
        "main.py --",
        "event_alert_send",
    )
    for item in forbidden:
        assert item not in module_text


def test_export_source_with_artifacts_fallback_and_archive_validation():
    import importlib.util
    import time
    import zipfile
    from datetime import datetime

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "export_source_with_artifacts",
        root / "scripts" / "export_source_with_artifacts.py",
    )
    assert spec and spec.loader
    export_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export_module)
    with TemporaryDirectory() as tmp:
        tree = Path(tmp) / "tree"
        tree.mkdir()
        (tree / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
        (tree / "crypto_rsi_scanner").mkdir()
        (tree / "crypto_rsi_scanner" / "unit.py").write_text("VALUE = 1\n", encoding="utf-8")
        (tree / ".env").write_text("SECRET=1\n", encoding="utf-8")
        (tree / "local.db").write_text("db\n", encoding="utf-8")
        out = Path(tmp) / "out.zip"
        assert export_module.main(root=tree, out=out) == 0
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
        assert "Makefile" in names
        assert "crypto_rsi_scanner/unit.py" in names
        assert ".env" not in names
        assert "local.db" not in names

        future_zip = Path(tmp) / "future.zip"
        now_ts = time.time()
        future = datetime.fromtimestamp(now_ts + 86400).timetuple()[:6]
        with zipfile.ZipFile(future_zip, "w") as zf:
            info = zipfile.ZipInfo("Makefile", future)
            zf.writestr(info, "all:\n\t@true\n")
        bad = export_module._validate_archive_entries(future_zip, safe_export_timestamp=now_ts)
        assert any(item.startswith("future_mtime:Makefile") for item in bad)


_EVENT_ALPHA_TEST_MODULES = (
    "tests.event_alpha.test_artifact_doctor",
    "tests.event_alpha.test_artifact_schema",
    "tests.event_alpha.test_integrated_radar",
    "tests.event_alpha.test_namespace_lifecycle",
    "tests.event_alpha.test_notifications",
    "tests.event_alpha.test_outcomes",
    "tests.event_alpha.test_provider_readiness",
    "tests.event_alpha.test_source_coverage",
)


def _iter_standalone_tests():
    import importlib

    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            yield __name__, name, value

    for module_name in _EVENT_ALPHA_TEST_MODULES:
        module = importlib.import_module(module_name)
        for name, value in sorted(vars(module).items()):
            if name.startswith("test_") and callable(value):
                yield module_name, name, value


def _call_standalone_test(fn):
    import copy
    import inspect
    from crypto_rsi_scanner import config

    kwargs = {}
    temp_dirs = []
    original_config = {}
    for config_name in dir(config):
        if not config_name.isupper():
            continue
        value = getattr(config, config_name)
        try:
            original_config[config_name] = copy.deepcopy(value)
        except Exception:  # noqa: BLE001
            original_config[config_name] = value
    for name, param in inspect.signature(fn).parameters.items():
        if param.default is not inspect.Parameter.empty:
            continue
        if name == "tmp_path":
            tmp = TemporaryDirectory()
            temp_dirs.append(tmp)
            kwargs[name] = Path(tmp.name)
            continue
        raise TypeError(f"unsupported standalone fixture: {name}")

    try:
        fn(**kwargs)
    finally:
        for config_name in tuple(dir(config)):
            if config_name.isupper() and config_name not in original_config:
                delattr(config, config_name)
        for config_name, value in original_config.items():
            setattr(config, config_name, value)
        for tmp in reversed(temp_dirs):
            tmp.cleanup()


def _run_all():
    funcs = list(_iter_standalone_tests())
    failures = 0
    for module_name, name, fn in funcs:
        label = name if module_name == __name__ else f"{module_name}.{name}"
        try:
            _call_standalone_test(fn)
            print(f"PASS {label}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {label}: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"ERROR {label}: {type(e).__name__}: {e}")
    print(f"\n{len(funcs) - failures}/{len(funcs)} passed")
    return failures


if __name__ == "__main__":
    if "--list-tests" in sys.argv:
        tests = list(_iter_standalone_tests())
        event_alpha_tests = sum(1 for module_name, _, _ in tests if module_name.startswith("tests.event_alpha."))
        print(f"standalone_tests={len(tests)}")
        print(f"event_alpha_tests={event_alpha_tests}")
        sys.exit(0)
    sys.exit(1 if _run_all() else 0)
