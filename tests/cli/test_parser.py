"""Focused pytest checks for CLI command snapshots."""

from __future__ import annotations

from crypto_rsi_scanner.cli.parser import classify_command


def test_classify_event_alpha_command():
    snapshot = classify_command(["--event-alpha-coinalyze-preflight"])
    assert snapshot.command_name == "event_alpha_coinalyze_preflight"
    assert snapshot.command_group == "provider_readiness"
