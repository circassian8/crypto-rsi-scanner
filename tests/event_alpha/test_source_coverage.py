"""Focused source-coverage package refactor tests."""

from __future__ import annotations

from datetime import datetime, timezone
from tempfile import TemporaryDirectory


def test_source_coverage_old_and_new_import_paths_resolve_same_objects():
    from crypto_rsi_scanner import event_alpha_source_coverage as old_source_coverage
    from crypto_rsi_scanner.event_alpha.radar import source_coverage as new_source_coverage

    assert old_source_coverage.build_source_coverage_report is new_source_coverage.build_source_coverage_report
    assert old_source_coverage.format_source_coverage_report is new_source_coverage.format_source_coverage_report
    assert old_source_coverage.LIVE_PROVIDER_READINESS_MD == new_source_coverage.LIVE_PROVIDER_READINESS_MD
    assert old_source_coverage.LIVE_PROVIDER_READINESS_JSON == new_source_coverage.LIVE_PROVIDER_READINESS_JSON


def test_source_coverage_links_live_provider_readiness_artifacts():
    from crypto_rsi_scanner import config, event_provider_status
    from crypto_rsi_scanner.event_alpha.radar import source_coverage

    with TemporaryDirectory() as tmp:
        report = source_coverage.build_source_coverage_report(
            provider_status_report=event_provider_status.build_event_discovery_provider_status(config),
            profile="fixture",
            artifact_namespace="pytest_source_coverage",
            artifact_namespace_dir=tmp,
            now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
        )

    payload = report.to_dict()
    text = source_coverage.format_source_coverage_report(report)
    readiness = payload["live_provider_activation_readiness_artifacts"]
    assert readiness["markdown"] == source_coverage.LIVE_PROVIDER_READINESS_MD
    assert readiness["json"] == source_coverage.LIVE_PROVIDER_READINESS_JSON
    assert "Live-provider activation readiness:" in text
    assert f"- readiness report: {source_coverage.LIVE_PROVIDER_READINESS_MD}" in text
    assert f"- readiness JSON: {source_coverage.LIVE_PROVIDER_READINESS_JSON}" in text
