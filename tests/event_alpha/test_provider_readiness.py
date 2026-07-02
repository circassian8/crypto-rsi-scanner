"""Focused provider/readiness package refactor tests."""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory


def test_provider_old_and_new_import_paths_resolve_same_objects():
    module_pairs = (
        ("crypto_rsi_scanner.event_coinalyze_preflight", "crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight", "build_preflight_report"),
        ("crypto_rsi_scanner.event_live_provider_readiness", "crypto_rsi_scanner.event_alpha.providers.live_provider_readiness", "build_readiness_report"),
        ("crypto_rsi_scanner.event_official_exchange", "crypto_rsi_scanner.event_alpha.providers.official_exchange", "run_official_exchange_scan"),
        ("crypto_rsi_scanner.event_official_exchange_activation", "crypto_rsi_scanner.event_alpha.providers.official_exchange_activation", "build_activation_report"),
        ("crypto_rsi_scanner.event_alpha_cryptopanic", "crypto_rsi_scanner.event_alpha.providers.cryptopanic", "build_cryptopanic_preflight"),
        ("crypto_rsi_scanner.event_provider_health", "crypto_rsi_scanner.event_alpha.providers.provider_health", "record_provider_success"),
        ("crypto_rsi_scanner.event_source_registry", "crypto_rsi_scanner.event_alpha.providers.source_registry", "assess_source"),
        ("crypto_rsi_scanner.event_source_packs", "crypto_rsi_scanner.event_alpha.providers.source_packs", "get_source_pack"),
        ("crypto_rsi_scanner.event_bybit_announcements_preflight", "crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight", "build_preflight_report"),
        ("crypto_rsi_scanner.event_unlock_calendar_preflight", "crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight", "build_preflight_report"),
        ("crypto_rsi_scanner.event_dex_onchain_readiness", "crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness", "run_dex_onchain_readiness"),
    )

    for old_path, new_path, attr in module_pairs:
        old_module = importlib.import_module(old_path)
        new_module = importlib.import_module(new_path)
        assert getattr(old_module, attr) is getattr(new_module, attr)


def test_coinalyze_preflight_smoke_new_package_path_writes_no_call_artifacts():
    from crypto_rsi_scanner.event_alpha.providers import coinalyze_preflight

    with TemporaryDirectory() as tmp:
        report = coinalyze_preflight.build_preflight_report(
            namespace_dir=tmp,
            smoke_mode=True,
            now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
        )
        json_path, md_path = coinalyze_preflight.write_preflight_artifacts(report, tmp)
        payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert report.live_call_allowed is False
    assert report.preflight_status in {"fixture_ready", "fixture_parser_failed"}
    assert payload["live_call_allowed"] is False
    assert payload["max_requests_per_run"] == 0
    assert any("no Telegram sends" in note for note in payload["safety_notes"])
    assert md_path.name == coinalyze_preflight.PREFLIGHT_MD


def test_live_provider_readiness_smoke_new_package_path_is_no_call():
    from crypto_rsi_scanner.event_alpha.providers import live_provider_readiness

    with TemporaryDirectory() as tmp:
        report = live_provider_readiness.build_readiness_report(
            profile="fixture",
            artifact_namespace="provider_readiness_pytest",
            smoke_mode=True,
            now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
        )
        json_path, md_path = live_provider_readiness.write_readiness_artifacts(report, tmp)
        payload = json.loads(json_path.read_text(encoding="utf-8"))

    providers = {row["provider_name"]: row for row in payload["providers"]}
    assert payload["live_calls_allowed"] is False
    assert providers["coinalyze"]["live_call_allowed"] is False
    assert providers["bybit_announcements_public"]["live_call_allowed"] is False
    assert providers["geckoterminal"]["live_call_allowed"] is False
    assert md_path.name == live_provider_readiness.READINESS_MD


def test_official_exchange_fixture_smoke_new_package_path_writes_candidates():
    from crypto_rsi_scanner.event_alpha.providers import official_exchange

    with TemporaryDirectory() as tmp:
        result = official_exchange.run_official_exchange_scan(
            namespace_dir=tmp,
            provider_paths={
                "binance_announcements": Path("fixtures/event_discovery/official_exchange_binance_announcements.json"),
                "bybit_announcements": Path("fixtures/event_discovery/official_exchange_bybit_announcements.json"),
            },
            profile="fixture",
            artifact_namespace="official_exchange_pytest",
            run_mode="fixture",
            run_id="pytest-official-exchange",
            observed_at="2026-06-15T16:00:00Z",
        )
        candidates = official_exchange.load_official_listing_candidates(tmp)

    by_symbol = {str(row.get("symbol") or ""): row for row in candidates}
    assert result.event_count >= 4
    assert result.candidate_count >= 4
    assert "TESTPERP" in by_symbol
    assert by_symbol["TESTPERP"]["research_only"] is True
    assert by_symbol["TESTPERP"]["created_alert"] is False
    assert by_symbol["TESTPERP"]["notification_send_enabled"] is False


def test_source_registry_and_source_packs_new_package_paths_classify_official_exchange():
    from crypto_rsi_scanner.event_alpha.providers import source_packs, source_registry

    assessment = source_registry.assess_source(
        provider="binance_announcements_public_or_fixture",
        source_url="https://www.binance.com/en/support/announcement/test",
        text="Binance will list TESTPERP perpetual contract.",
        mission=source_registry.SourceMission.OFFICIAL_CONFIRMATION,
    )
    pack = source_packs.get_source_pack("official_exchange_listing_pack")
    pack_eval = source_packs.evaluate_pack_evidence(
        {
            "provider": "binance_announcements_public_or_fixture",
            "source_url": "https://www.binance.com/en/support/announcement/test",
            "title": "Binance will list TESTPERP",
            "source_class": source_registry.SourceClass.OFFICIAL_EXCHANGE.value,
            "market_confirmation_score": 75,
        },
        pack=pack,
    )

    assert assessment.source_class == source_registry.SourceClass.OFFICIAL_EXCHANGE.value
    assert pack.name == "official_exchange_listing_pack"
    assert pack_eval["source_pack"] == "official_exchange_listing_pack"
    assert pack_eval["source_pack_preferred_source_present"] is True
