"""Runtime parity for Event Alpha evidence-provider authorization."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from crypto_rsi_scanner import config
from crypto_rsi_scanner.cli.services import event_alpha_research
from crypto_rsi_scanner.cli.services.scanner_parts import config_reports
from crypto_rsi_scanner.event_alpha.providers import provider_health
from crypto_rsi_scanner.event_alpha.radar import catalyst_search
from crypto_rsi_scanner.event_alpha.radar.evidence.models import (
    EvidenceAcquisitionConfig,
)
from crypto_rsi_scanner.event_alpha.radar.evidence.provider_contract import (
    CURRENT_AUTHORIZATION_ENV_BY_SETTING,
    PLANNER_PROVIDER_HINTS,
)


NOW = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)


def _clear_runtime_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for setting, env_name in CURRENT_AUTHORIZATION_ENV_BY_SETTING.items():
        monkeypatch.delenv(env_name, raising=False)
        monkeypatch.setattr(config, setting, False)
    for attr in (
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH",
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH",
        "EVENT_DISCOVERY_COINMARKETCAL_PATH",
        "EVENT_DISCOVERY_TOKENOMIST_PATH",
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH",
        "EVENT_DISCOVERY_GDELT_PATH",
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH",
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH",
    ):
        monkeypatch.setattr(config, attr, None)
    monkeypatch.setattr(config, "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS", ())
    monkeypatch.setattr(config, "EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN", "")
    monkeypatch.setattr(config, "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY", "")
    monkeypatch.setattr(config, "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET", "")
    monkeypatch.setattr(config, "EVENT_PROVIDER_HEALTH_PATH", tmp_path / "provider-health.json")
    monkeypatch.setattr(config, "EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF", False)


def _profile_with_authorization_overrides() -> SimpleNamespace:
    overrides = {
        setting: True for setting in CURRENT_AUTHORIZATION_ENV_BY_SETTING
    }
    overrides["EVENT_LLM_PROVIDER"] = "openai"
    overrides["EVENT_LLM_EXTRACTOR_PROVIDER"] = "openai"
    overrides["EVENT_LLM_CATALYST_FRAMES_PROVIDER"] = "openai"
    return SimpleNamespace(
        name="test_live_profile",
        config_overrides=overrides,
    )


def test_live_profile_capability_cannot_create_provider_or_llm_authorization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_runtime_sources(monkeypatch, tmp_path)
    monkeypatch.setattr(
        config_reports.event_alpha_profiles,
        "get_profile",
        lambda name: _profile_with_authorization_overrides(),
    )
    monkeypatch.setattr(config_reports, "_apply_event_alpha_artifact_context", lambda name: None)
    monkeypatch.setattr(config_reports, "_normalize_profile_paths", lambda: None)

    config_reports._apply_event_alpha_profile("test_live_profile")

    assert all(
        getattr(config, setting) is False
        for setting in CURRENT_AUTHORIZATION_ENV_BY_SETTING
    )


def test_notify_llm_quality_without_stage_authorization_builds_no_openai_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_runtime_sources(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "present-but-not-authorized")
    monkeypatch.setattr(
        config_reports,
        "_apply_event_alpha_artifact_context",
        lambda name: None,
    )
    monkeypatch.setattr(config_reports, "_normalize_profile_paths", lambda: None)

    config_reports._apply_event_alpha_profile("notify_llm_quality")
    llm_inputs = event_alpha_research._event_alpha_cycle_llm_inputs(True)

    assert config.EVENT_LLM_ENABLED is False
    assert config.EVENT_LLM_EXTRACTOR_ENABLED is False
    assert config.EVENT_LLM_CATALYST_FRAMES_ENABLED is False
    assert llm_inputs["relationship_provider"] is None
    assert llm_inputs["extraction_provider"] is None
    assert llm_inputs["catalyst_frame_provider"] is None


def test_live_profile_preserves_only_matching_existing_authorizations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_runtime_sources(monkeypatch, tmp_path)
    monkeypatch.setenv("RSI_EVENT_DISCOVERY_GDELT_LIVE", "1")
    monkeypatch.setenv("RSI_EVENT_LLM_ENABLED", "true")
    monkeypatch.setenv("RSI_EVENT_LLM_EXTRACTOR_ENABLED", "yes")
    monkeypatch.setattr(
        config_reports.event_alpha_profiles,
        "get_profile",
        lambda name: _profile_with_authorization_overrides(),
    )
    monkeypatch.setattr(config_reports, "_apply_event_alpha_artifact_context", lambda name: None)
    monkeypatch.setattr(config_reports, "_normalize_profile_paths", lambda: None)

    config_reports._apply_event_alpha_profile("test_live_profile")

    assert config.EVENT_DISCOVERY_GDELT_LIVE is True
    assert config.EVENT_LLM_ENABLED is True
    assert config.EVENT_LLM_EXTRACTOR_ENABLED is True
    assert config.EVENT_LLM_CATALYST_FRAMES_ENABLED is False
    assert config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE is False
    assert config.EVENT_DISCOVERY_UNIVERSE_LIVE is False
    assert config.EVENT_DISCOVERY_COINALYZE_LIVE is False


def test_offline_fixture_llm_profile_does_not_require_live_authorization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_runtime_sources(monkeypatch, tmp_path)
    monkeypatch.setattr(
        config_reports.event_alpha_profiles,
        "get_profile",
        lambda name: SimpleNamespace(
            name="offline_fixture_llm",
            config_overrides={
                "EVENT_LLM_ENABLED": True,
                "EVENT_LLM_PROVIDER": "fixture",
            },
        ),
    )
    monkeypatch.setattr(
        config_reports,
        "_apply_event_alpha_artifact_context",
        lambda name: None,
    )
    monkeypatch.setattr(config_reports, "_normalize_profile_paths", lambda: None)

    config_reports._apply_event_alpha_profile("offline_fixture_llm")

    assert config.EVENT_LLM_ENABLED is True
    assert config.EVENT_LLM_PROVIDER == "fixture"


def test_live_evidence_dispatch_has_no_fixture_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_runtime_sources(monkeypatch, tmp_path)

    providers = event_alpha_research._event_evidence_acquisition_providers_from_runtime(
        EvidenceAcquisitionConfig(enabled=True, fixture_only=False)
    )

    assert set(PLANNER_PROVIDER_HINTS) <= set(providers)
    assert providers["default"] is None
    assert providers["fixture"] is None
    assert providers["coinalyze"] is None
    assert providers["sports_fixtures"] is None
    assert all(provider is None for provider in providers.values())


def test_live_evidence_dispatch_rejects_fixture_path_but_accepts_operator_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_runtime_sources(monkeypatch, tmp_path)
    fixture_path = tmp_path / "fixtures" / "gdelt.json"
    fixture_path.parent.mkdir()
    fixture_path.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(config, "EVENT_DISCOVERY_GDELT_PATH", fixture_path)

    rejected = event_alpha_research._event_evidence_acquisition_providers_from_runtime(
        EvidenceAcquisitionConfig(enabled=True, fixture_only=False)
    )
    assert rejected["gdelt"] is None

    operator_path = tmp_path / "operator_downloads" / "gdelt.json"
    operator_path.parent.mkdir()
    operator_path.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(config, "EVENT_DISCOVERY_GDELT_PATH", operator_path)
    accepted = event_alpha_research._event_evidence_acquisition_providers_from_runtime(
        EvidenceAcquisitionConfig(enabled=True, fixture_only=False)
    )

    assert isinstance(accepted["gdelt"], provider_health.HealthCheckedProvider)
    assert accepted["gdelt"].name == "gdelt"
    assert accepted["gdelt"].provider_role == "event_source"


def test_explicit_live_gdelt_uses_existing_event_source_backoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_runtime_sources(monkeypatch, tmp_path)
    monkeypatch.setenv("RSI_EVENT_DISCOVERY_GDELT_LIVE", "1")
    monkeypatch.setattr(config, "EVENT_DISCOVERY_GDELT_LIVE", True)
    health_cfg = provider_health.EventProviderHealthConfig(
        path=config.EVENT_PROVIDER_HEALTH_PATH,
        max_consecutive_failures=1,
        backoff_minutes=30,
    )
    provider_health.record_provider_failure(
        "gdelt",
        "rate_limited status=429",
        cfg=health_cfg,
        now=NOW,
        provider_service="gdelt",
        provider_role="event_source",
        provider_kind="event_source",
    )
    providers = event_alpha_research._event_evidence_acquisition_providers_from_runtime(
        EvidenceAcquisitionConfig(enabled=True, fixture_only=False)
    )
    gdelt = providers["gdelt"]
    assert isinstance(gdelt, provider_health.HealthCheckedProvider)

    result = gdelt.search(
        (
            catalyst_search.SearchQuery(
                anomaly_raw_id="anomaly:one",
                query="TEST catalyst",
                symbol="TEST",
                rank=1,
            ),
        ),
        max_results_per_query=1,
        now=NOW,
    )

    assert result.provider_fetch_count == 0
    assert any("backoff" in warning for warning in result.warnings)


def test_fixture_only_dispatch_remains_explicitly_fixture_backed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_runtime_sources(monkeypatch, tmp_path)
    providers = event_alpha_research._event_evidence_acquisition_providers_from_runtime(
        EvidenceAcquisitionConfig(enabled=True, fixture_only=True)
    )

    assert all(
        getattr(providers[hint], "name", None) == "fixture"
        for hint in PLANNER_PROVIDER_HINTS
    )
