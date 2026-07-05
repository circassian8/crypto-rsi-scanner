"""Canonical Event Alpha import smoke tests."""

from __future__ import annotations

import importlib


CANONICAL_EVENT_ALPHA_MODULES = (
    "crypto_rsi_scanner.event_alpha.artifacts.context",
    "crypto_rsi_scanner.event_alpha.artifacts.paths",
    "crypto_rsi_scanner.event_alpha.artifacts.run_ledger",
    "crypto_rsi_scanner.event_alpha.artifacts.retention",
    "crypto_rsi_scanner.event_alpha.artifacts.locks",
    "crypto_rsi_scanner.event_alpha.doctor.artifact_doctor",
    "crypto_rsi_scanner.event_alpha.config.profiles",
    "crypto_rsi_scanner.event_alpha.config.v1_readiness",
    "crypto_rsi_scanner.event_alpha.config.preflight",
    "crypto_rsi_scanner.event_alpha.notifications.pipeline",
    "crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight",
    "crypto_rsi_scanner.event_alpha.radar.integrated_radar",
)


def test_canonical_event_alpha_import_paths_work():
    for module_name in CANONICAL_EVENT_ALPHA_MODULES:
        module = importlib.import_module(module_name)
        assert module is not None
