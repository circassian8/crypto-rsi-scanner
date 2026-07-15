"""Proof that ordinary Event Alpha tests cannot consume the cumulative repo cache."""

from __future__ import annotations

import os
from pathlib import Path

from crypto_rsi_scanner import config
from crypto_rsi_scanner.event_alpha.artifacts.context import context_from_profile


def test_default_event_alpha_artifact_roots_are_per_test_temporary_paths(tmp_path):
    artifact_base = Path(config.EVENT_ALPHA_ARTIFACT_BASE_DIR)
    discovery_cache = Path(config.EVENT_DISCOVERY_CACHE_DIR)

    assert artifact_base.is_relative_to(tmp_path)
    assert discovery_cache.is_relative_to(tmp_path)
    assert artifact_base.name == "event-alpha-artifacts"
    assert discovery_cache.name == "event-discovery-cache"
    assert Path(os.environ["RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR"]) == artifact_base
    assert Path(os.environ["RSI_EVENT_DISCOVERY_CACHE_DIR"]) == discovery_cache
    assert Path(config.EVENT_ALPHA_ALERT_STORE_PATH).is_relative_to(discovery_cache)
    assert Path(config.EVENT_ALPHA_RUN_LEDGER_PATH).is_relative_to(discovery_cache)
    assert Path(config.EVENT_SOURCE_ENRICHMENT_CACHE_DIR).is_relative_to(discovery_cache)
    assert Path(config.EVENT_DISCOVERY_CRYPTOPANIC_REQUEST_LEDGER_PATH).is_relative_to(discovery_cache)
    assert "RSI_EVENT_ALPHA_ALERT_STORE_PATH" not in os.environ
    assert "RSI_EVENT_DISCOVERY_CRYPTOPANIC_REQUEST_LEDGER_PATH" not in os.environ
    assert "RSI_EVENT_ALPHA_NOTIFICATION_DELIVERIES_PATH" not in os.environ
    assert not artifact_base.exists()
    assert not discovery_cache.exists()


def test_explicit_artifact_base_overrides_global_test_isolation(tmp_path):
    explicit = tmp_path / "explicit-artifacts"

    context = context_from_profile(
        "fixture",
        artifact_namespace="explicit",
        base_dir=explicit,
    )

    assert context.base_dir == explicit
    assert context.namespace_dir == explicit / "explicit"
    assert context.alert_store_path == explicit / "explicit" / "event_alpha_alerts.jsonl"
    assert context.run_ledger_path == explicit / "explicit" / "event_alpha_runs.jsonl"


def test_per_test_artifact_path_override_still_wins_after_global_isolation(tmp_path, monkeypatch):
    explicit = tmp_path / "explicit-artifacts"
    explicit_alert_store = tmp_path / "per-test-alerts.jsonl"
    monkeypatch.setenv("RSI_EVENT_ALPHA_ALERT_STORE_PATH", str(explicit_alert_store))

    context = context_from_profile(
        "fixture",
        artifact_namespace="explicit",
        base_dir=explicit,
    )

    assert context.base_dir == explicit
    assert context.alert_store_path == explicit_alert_store
