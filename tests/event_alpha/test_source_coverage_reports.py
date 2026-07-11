"""Source-coverage imports, readiness links, reports, and doctor regressions."""

from __future__ import annotations

from datetime import datetime, timezone
from tempfile import TemporaryDirectory

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_source_coverage_canonical_import_paths_resolve_same_objects():
    import crypto_rsi_scanner.event_alpha.radar.source_coverage as direct_source_coverage
    from crypto_rsi_scanner.event_alpha.radar import source_coverage as new_source_coverage

    assert direct_source_coverage.build_source_coverage_report is new_source_coverage.build_source_coverage_report
    assert direct_source_coverage.format_source_coverage_report is new_source_coverage.format_source_coverage_report
    assert direct_source_coverage.LIVE_PROVIDER_READINESS_MD == new_source_coverage.LIVE_PROVIDER_READINESS_MD
    assert direct_source_coverage.LIVE_PROVIDER_READINESS_JSON == new_source_coverage.LIVE_PROVIDER_READINESS_JSON


def test_source_coverage_cryptopanic_exact_run_semantics():
    import json
    from pathlib import Path

    import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status
    import crypto_rsi_scanner.event_alpha.radar.source_coverage as source_coverage

    provider_report = event_provider_status.build_event_discovery_provider_status(
        _event_provider_status_cfg(
            EVENT_DISCOVERY_CRYPTOPANIC_LIVE=False,
            EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN="configured_test_value",
        )
    )
    run_id = "run-profile-disabled"
    readiness = {
        "run_id": run_id,
        "providers": [{
            "provider": "cryptopanic_rss_gdelt_context",
            "provider_health_key": "cryptopanic",
            "configured": True,
            "live_call_allowed": False,
        }],
    }
    profile_disabled = source_coverage.build_source_coverage_report(
        provider_status_report=provider_report,
        exact_run_row={
            "run_id": run_id,
            "cryptopanic_configured": True,
            "cryptopanic_attempted": False,
            "cryptopanic_skip_reason": "profile_disabled",
        },
        provider_readiness_payload=readiness,
        cryptopanic_configured_fallback=True,
    )
    assert profile_disabled.cryptopanic_configured is True
    assert profile_disabled.cryptopanic_selected_for_run is False
    assert profile_disabled.cryptopanic_live_call_allowed is False
    assert profile_disabled.cryptopanic_observed is False
    assert profile_disabled.cryptopanic_not_used_reason == "profile_disabled"
    assert profile_disabled.cryptopanic_coverage_status == "configured_profile_disabled"
    assert "explicit no-send evidence/candidate profile" in str(profile_disabled.cryptopanic_recommendation)
    proxy = {pack.source_pack: pack for pack in profile_disabled.packs}["proxy_preipo_rwa_pack"]
    assert "cryptopanic" in proxy.configured_providers
    assert "cryptopanic" not in proxy.missing_providers
    assert not any("CryptoPanic token" in action for action in proxy.recommended_actions)

    selected_disabled = source_coverage.build_source_coverage_report(
        provider_status_report=provider_report,
        exact_run_row={
            "run_id": "run-selected-disabled",
            "cryptopanic_configured": True,
            "cryptopanic_attempted": False,
            "cryptopanic_skip_reason": "live_calls_disabled",
        },
        provider_readiness_payload={
            **readiness,
            "run_id": "run-selected-disabled",
        },
    )
    assert selected_disabled.cryptopanic_selected_for_run is True
    assert selected_disabled.cryptopanic_live_call_allowed is False
    assert selected_disabled.cryptopanic_coverage_status == "configured_selected_live_disabled"

    with TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "cryptopanic_request_ledger.jsonl"
        ledger.write_text(json.dumps({
            "timestamp": "2026-06-15T12:00:00+00:00",
            "status_code": 200,
            "result_count": 1,
            "quota_counted": True,
            "currencies": "RUNE",
            "normalized_request_key": "cryptopanic:RUNE",
            "request_url_redacted": "https://cryptopanic.test/posts/?auth_token=<redacted>&currencies=RUNE",
        }) + "\n", encoding="utf-8")
        observed = source_coverage.build_source_coverage_report(
            provider_status_report=provider_report,
            exact_run_row={
                "run_id": "run-observed",
                "cryptopanic_configured": True,
                "cryptopanic_attempted": True,
            },
            provider_readiness_payload={
                "run_id": "run-observed",
                "providers": [{
                    "provider_health_key": "cryptopanic",
                    "configured": True,
                    "live_call_allowed": True,
                }],
            },
            evidence_acquisition_rows=[{
                "source_pack": "security_shock_pack",
                "status": "accepted_evidence_found",
                "accepted_evidence": [{"provider": "cryptopanic"}],
            }],
            cryptopanic_request_ledger_path=ledger,
            now=datetime(2026, 6, 15, 13, tzinfo=timezone.utc),
        )
    assert observed.cryptopanic_selected_for_run is True
    assert observed.cryptopanic_live_call_allowed is True
    assert observed.cryptopanic_observed is True
    assert observed.cryptopanic_coverage_status == "observed_healthy"

    missing = source_coverage.build_source_coverage_report(
        provider_status_report=event_provider_status.build_event_discovery_provider_status(
            _event_provider_status_cfg()
        ),
        exact_run_row={"run_id": "run-missing", "cryptopanic_configured": False},
        provider_readiness_payload={
            "run_id": "run-missing",
            "providers": [{"provider_health_key": "cryptopanic", "configured": False, "live_call_allowed": False}],
        },
        cryptopanic_configured_fallback=False,
    )
    assert missing.cryptopanic_configured is False
    assert missing.cryptopanic_coverage_status == "not_configured"
    assert "configure CryptoPanic token" in str(missing.cryptopanic_recommendation)


def test_source_coverage_counts_explicit_blockers_and_collapses_visible_families():
    from types import SimpleNamespace

    import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status
    import crypto_rsi_scanner.event_alpha.radar.source_coverage as source_coverage

    provider_report = event_provider_status.build_event_discovery_provider_status(_event_provider_status_cfg())
    duplicate_rows = [
        {
            "core_opportunity_id": f"core-duplicate-{index}",
            "coin_id": "story-2",
            "symbol": "DATA",
            "primary_impact_path": "strategic_investment",
            "source_pack": "strategic_investment_pack",
            "source_requirements_met": False,
            "source_pack_confirmation_status": "coverage_gap",
            "why_not_alertable": ["strong_source_missing"],
            "evidence_acquisition_status": "not_executed",
            "accepted_evidence_count": 0,
            "market_context_freshness_status": "missing",
        }
        for index in range(2)
    ]
    rows = [
        *duplicate_rows,
        {
            "core_opportunity_id": "core-official",
            "coin_id": "asset-official",
            "symbol": "OFF",
            "primary_impact_path": "listing_liquidity_event",
            "source_pack": "listing_liquidity_pack",
            "source_requirements_met": False,
            "why_not_alertable": ["official_exchange_source_required"],
            "evidence_acquisition_status": "not_executed",
            "accepted_evidence_count": 0,
            "market_context_freshness_status": "fresh",
        },
        {
            "core_opportunity_id": "core-structured",
            "coin_id": "asset-structured",
            "symbol": "LOCK",
            "primary_impact_path": "unlock_supply_event",
            "source_pack": "unlock_supply_pack",
            "source_requirements_met": False,
            "why_not_alertable": ["structured_unlock_source_required"],
            "evidence_acquisition_status": "not_executed",
            "accepted_evidence_count": 0,
            "market_context_freshness_status": "stale",
        },
    ]
    report = source_coverage.build_source_coverage_report(
        provider_status_report=provider_report,
        core_opportunity_rows=rows,
        near_miss_candidates=[SimpleNamespace(
            near_miss_id="near-source-search",
            core_opportunity_id="core-duplicate-0",
            coin_id="story-2",
            symbol="DATA",
            source_pack="strategic_investment_pack",
            recommended_refresh_actions=("targeted_evidence_refresh", "source_pack_search"),
        )],
    )
    assert report.candidates_blocked_by_source_coverage == 4
    assert report.candidates_blocked_by_missing_strong_source == 2
    assert report.candidates_blocked_by_missing_official_source == 1
    assert report.candidates_blocked_by_missing_structured_source == 1
    assert report.candidates_blocked_by_evidence_not_acquired == 4
    assert report.candidates_blocked_by_provider_unavailable == 0
    assert report.candidates_blocked_by_market_context == 3
    assert report.candidate_families_blocked_by_source_coverage == 3
    assert report.candidate_families_blocked_by_market_coverage == 2
    proxy_pack = {pack.source_pack: pack for pack in report.packs}["proxy_preipo_rwa_pack"]
    assert proxy_pack.evidence_absence_meaningful is False
    text = source_coverage.format_source_coverage_report(report)
    assert "evidence absence remains non-negative proof" in text


def test_source_coverage_doctor_blocks_exact_run_semantic_contradictions():
    import json
    from pathlib import Path

    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as artifact_doctor

    run = {
        "run_id": "run-doctor-profile-disabled",
        "profile": "notify_no_key",
        "artifact_namespace": "notify_no_key",
        "run_mode": "test",
        "cryptopanic_configured": True,
        "cryptopanic_attempted": False,
        "cryptopanic_skip_reason": "profile_disabled",
    }
    core = {
        "run_id": run["run_id"],
        "profile": run["profile"],
        "artifact_namespace": run["artifact_namespace"],
        "run_mode": "test",
        "core_opportunity_id": "core-doctor-source-gap",
        "source_pack": "strategic_investment_pack",
        "source_requirements_met": False,
        "why_not_alertable": ["strong_source_missing"],
    }
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        report_path = base / "event_alpha_source_coverage.md"
        report_path.write_text("CryptoPanic:\n- configured: false\n", encoding="utf-8")
        (base / "event_alpha_source_coverage.json").write_text(json.dumps({
            "run_id": run["run_id"],
            "cryptopanic_configured": False,
            "cryptopanic_not_used_reason": "not_configured",
            "cryptopanic_coverage_status": "not_configured",
            "cryptopanic_recommendation": "configure CryptoPanic API token",
            "candidates_blocked_by_source_coverage": 0,
        }), encoding="utf-8")
        (base / "event_live_provider_activation_readiness.json").write_text(json.dumps({
            "run_id": run["run_id"],
            "providers": [{
                "provider_health_key": "cryptopanic",
                "configured": True,
                "live_call_allowed": False,
            }],
        }), encoding="utf-8")
        bad = artifact_doctor.diagnose_artifacts(
            run_rows=[run],
            core_opportunity_rows=[core],
            source_coverage_report_path=report_path,
            profile=run["profile"],
            artifact_namespace=run["artifact_namespace"],
            include_test_artifacts=True,
            strict=True,
        )
        assert bad.cryptopanic_run_coverage_config_mismatch == 1
        assert bad.cryptopanic_profile_disabled_coverage_mismatch == 1
        assert bad.cryptopanic_profile_disabled_credential_recommendation == 1
        assert bad.source_coverage_blocker_summary_inconsistent == 1

        (base / "event_alpha_source_coverage.json").write_text(json.dumps({
            "run_id": run["run_id"],
            "cryptopanic_configured": True,
            "cryptopanic_selected_for_run": False,
            "cryptopanic_live_call_allowed": False,
            "cryptopanic_not_used_reason": "profile_disabled",
            "cryptopanic_coverage_status": "configured_profile_disabled",
            "cryptopanic_recommendation": "enable CryptoPanic in an explicit no-send evidence/candidate profile if desired",
            "candidates_blocked_by_source_coverage": 1,
        }), encoding="utf-8")
        good = artifact_doctor.diagnose_artifacts(
            run_rows=[run],
            core_opportunity_rows=[core],
            source_coverage_report_path=report_path,
            profile=run["profile"],
            artifact_namespace=run["artifact_namespace"],
            include_test_artifacts=True,
            strict=True,
        )
        assert good.cryptopanic_run_coverage_config_mismatch == 0
        assert good.cryptopanic_profile_disabled_coverage_mismatch == 0
        assert good.cryptopanic_profile_disabled_credential_recommendation == 0
        assert good.source_coverage_blocker_summary_inconsistent == 0


def test_source_coverage_links_live_provider_readiness_artifacts():
    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status
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


def test_event_alpha_source_coverage_report_groups_pack_provider_and_evidence_gaps():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.providers.cryptopanic as event_alpha_cryptopanic
    import crypto_rsi_scanner.event_alpha.radar.source_coverage as event_alpha_source_coverage

    cfg = _event_provider_status_cfg(
        EVENT_DISCOVERY_GDELT_LIVE=True,
        EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=True,
        EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS=("https://example.test/rss",),
        EVENT_DISCOVERY_UNIVERSE_LIVE=True,
    )
    provider_report = event_provider_status.build_event_discovery_provider_status(cfg)
    provider_health_rows = {
        "gdelt:event_source": {
            "provider_service": "gdelt",
            "provider_role": "event_source",
            "consecutive_failures": 2,
        },
        "rss:catalyst_search": {
            "provider_service": "rss",
            "provider_role": "catalyst_search",
            "consecutive_failures": 1,
        },
        "coingecko:universe": {
            "provider_service": "coingecko",
            "provider_role": "universe",
            "consecutive_failures": 0,
        },
    }
    acquisition_rows = [
        {
            "source_pack": "proxy_preipo_rwa_pack",
            "status": "skipped_budget",
            "symbol": "VELVET",
        },
        {
            "source_pack": "security_shock_pack",
            "status": "accepted_evidence_found",
            "symbol": "RUNE",
            "providers_used": ("cryptopanic",),
            "accepted_evidence": [{
                "provider": "cryptopanic",
                "source_class": "cryptopanic_tagged",
                "title": "RUNE exploit update",
                "reason_codes": ("cryptopanic_currency_tag_match", "direct_token_mechanism"),
                "currency_tags": ("RUNE",),
                "source_enrichment": {
                    "article_quality_status": "good",
                    "cleaner_version": "source_enrichment_cleaner_test",
                    "boilerplate_ratio": 0.1,
                },
            }],
        },
        {
            "source_pack": "listing_liquidity_pack",
            "status": "rejected_results_only",
            "symbol": "TEST",
        },
        {
            "source_pack": "perp_listing_squeeze_pack",
            "status": "provider_unavailable",
            "symbol": "PERP",
        },
    ]
    core_rows = [
        {
            "source_pack": "proxy_preipo_rwa_pack",
            "symbol": "VELVET",
            "live_confirmation_reason": "source_pack_confirmation_missing",
        },
    ]

    report = event_alpha_source_coverage.build_source_coverage_report(
        provider_status_report=provider_report,
        provider_health_rows=provider_health_rows,
        evidence_acquisition_rows=acquisition_rows,
        core_opportunity_rows=core_rows,
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep",
    )
    assert report.cryptopanic_configured is False
    assert report.cryptopanic_observed is True
    assert report.cryptopanic_accepted_evidence == 1
    assert report.cryptopanic_rejected_evidence == 0
    assert report.cryptopanic_source_packs == ("security_shock_pack",)
    payload = report.to_dict()
    categories = payload["category_priorities"]
    assert categories[0]["category"] == "Derivatives/OI/funding"
    assert "coinalyze" in categories[0]["providers"]
    assert categories[1]["category"] == "Official exchange announcements"
    assert categories[-2]["category"] == "CryptoPanic context"
    assert categories[-1]["category"] == "RSS/GDELT context only"
    by_pack = {pack.source_pack: pack for pack in report.packs}
    proxy = by_pack["proxy_preipo_rwa_pack"]
    security = by_pack["security_shock_pack"]
    listing = by_pack["listing_liquidity_pack"]
    market = by_pack["market_anomaly_pack"]
    perp = by_pack["perp_listing_squeeze_pack"]

    assert "cryptopanic" in proxy.missing_providers
    assert "gdelt" in proxy.degraded_or_backoff_providers
    assert "project_blog_rss" in proxy.degraded_or_backoff_providers
    assert proxy.provider_coverage_status == "degraded"
    assert "source_pack_coverage_degraded" in str(proxy.coverage_gap_reason)
    assert "cryptopanic" in proxy.providers_missing_for_confirmation
    assert "project_blog_rss" in proxy.providers_degraded_for_confirmation
    assert "project_blog_rss:catalyst_search=degraded" in proxy.provider_role_statuses
    assert proxy.evidence_absence_meaningful is False
    assert proxy.skipped_budget_count == 1
    assert proxy.candidates_blocked_by_coverage_gap == 2
    assert any("CryptoPanic" in item for item in proxy.recommended_actions)
    assert any("RSS" in item or "project/blog RSS" in item for item in proxy.recommended_actions)
    assert any("evidence-acquisition query/candidate budget" in item for item in proxy.recommended_actions)
    assert security.accepted_evidence_count == 1
    assert "good=1" in security.article_quality_counts
    assert "cryptopanic" in security.missing_providers
    assert listing.provider_coverage_status == "not_configured"
    assert listing.rejected_only_count == 1
    assert any("rejected evidence samples" in item for item in listing.recommended_actions)
    assert perp.provider_coverage_status == "unavailable"
    assert perp.provider_unavailable_count == 1
    assert any("provider health report/reset" in item for item in perp.recommended_actions)
    assert "coingecko" in market.healthy_providers
    assert "defillama" in market.missing_providers
    assert market.provider_coverage_status == "partial"
    assert any("DefiLlama" in item for item in market.recommended_actions)
    assert market.evidence_absence_meaningful is True

    text = event_alpha_source_coverage.format_source_coverage_report(report)
    assert "EVENT ALPHA SOURCE COVERAGE" in text
    assert "CryptoPanic:" in text
    assert "- configured: false" in text
    assert "- observed this run: true" in text
    assert "- accepted evidence: 1" in text
    assert "- source packs contributed: security_shock_pack" in text
    assert "proxy_preipo_rwa_pack" in text
    assert "missing providers: cryptopanic" in text
    assert "provider coverage status: degraded" in text
    assert "provider role health: gdelt:event_source=degraded, project_blog_rss:catalyst_search=degraded" in text
    assert "providers missing for confirmation: coinalyze, cryptopanic, geckoterminal, polymarket" in text
    assert "evidence absence meaningful: false" in text
    assert "accepted=1" in text
    assert "article quality: good=1" in text
    assert "Most useful next data source categories:" in text
    assert "1. Derivatives/OI/funding" in text
    assert "2. Official exchange announcements" in text
    assert "Live-provider activation readiness:" in text
    assert "event_live_provider_activation_readiness.md" in text
    assert "next activation plan" in text
    assert "Most useful next data source:" in text
    assert event_alpha_source_coverage._provider_lane_priority("coinalyze") > event_alpha_source_coverage._provider_lane_priority("gdelt")  # noqa: SLF001
    assert event_alpha_source_coverage._provider_lane_priority("binance_announcements") > event_alpha_source_coverage._provider_lane_priority("project_blog_rss")  # noqa: SLF001
    assert "recommended actions:" in text
    assert "configure CryptoPanic token/news coverage" in text
    assert "RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN" in text
    assert "No alerts, sends, trades" in text

    configured_cfg = _event_provider_status_cfg(
        EVENT_DISCOVERY_CRYPTOPANIC_LIVE=True,
        EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN="SECRET_TOKEN_SHOULD_NOT_RENDER",
    )
    configured_report = event_provider_status.build_event_discovery_provider_status(configured_cfg)
    preflight = event_alpha_cryptopanic.build_cryptopanic_preflight(
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep",
        provider_status_report=configured_report,
        provider_health_rows={
            "cryptopanic:catalyst_search": {
                "provider_key": "cryptopanic:catalyst_search",
                "provider_service": "cryptopanic",
                "provider_role": "catalyst_search",
                "disabled_until": "2999-01-01T00:00:00+00:00",
                "last_error_class": "HTTPError",
            }
        },
        provider_health_path="event_fade_cache/notify_llm_deep/event_provider_health.json",
        request_ledger_path=None,
        token_configured=True,
        live_enabled=True,
        endpoint_url="https://cryptopanic.com/api/growth_weekly/v2",
        plan="growth_weekly",
        weekly_limit=600,
        daily_soft_limit=80,
        per_run_limit=20,
        catalyst_search_providers=("cryptopanic", "gdelt"),
        no_send=True,
        now=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )
    preflight_text = event_alpha_cryptopanic.format_cryptopanic_preflight(preflight)
    assert preflight.token_configured is True
    assert preflight.provider_in_backoff is True
    assert preflight.skip_reason == "provider_backoff"
    assert preflight.status == "IN_BACKOFF"
    assert "CryptoPanic token configured: yes (redacted)" in preflight_text
    assert "endpoint: https://cryptopanic.com/api/growth_weekly/v2/posts/" in preflight_text
    assert "plan: growth_weekly" in preflight_text
    assert "weekly usage: 0/600" in preflight_text
    assert "SECRET_TOKEN_SHOULD_NOT_RENDER" not in preflight_text
    assert "security_shock_pack" in preflight.source_packs
    assert "proxy_preipo_rwa_pack" in preflight.source_packs
    assert "make event-alpha-provider-health-reset PROFILE=notify_llm_deep SERVICE=cryptopanic CONFIRM=1" in preflight_text

    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        core_opportunity_rows=[
            {
                "profile": "notify_llm_deep",
                "artifact_namespace": "notify_llm_deep",
                "run_mode": "test",
                "core_opportunity_id": "agg:bad-source-coverage",
                "source_pack": "proxy_preipo_rwa_pack",
                "provider_coverage_status": "degraded",
                "evidence_absence_is_meaningful": True,
                "providers_missing_for_confirmation": ("cryptopanic",),
            }
        ],
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep",
        include_test_artifacts=True,
        strict=True,
    )
    assert doctor.degraded_provider_absence_marked_meaningful == 1
    assert doctor.missing_provider_recommendations_missing == 1

    unobserved = event_alpha_source_coverage.build_source_coverage_report(
        provider_status_report=provider_report,
        provider_health_rows={},
        evidence_acquisition_rows=[],
        core_opportunity_rows=[],
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep",
    )
    unobserved_proxy = {pack.source_pack: pack for pack in unobserved.packs}["proxy_preipo_rwa_pack"]
    assert "gdelt" in unobserved_proxy.unknown_or_unobserved_providers
    assert "project_blog_rss" in unobserved_proxy.unknown_or_unobserved_providers
    assert "gdelt" not in unobserved_proxy.healthy_providers
    assert unobserved_proxy.provider_coverage_status == "skipped_live_calls_disabled"
    assert "gdelt:not_observed=skipped_live_calls_disabled" in unobserved_proxy.provider_role_statuses
    unobserved_text = event_alpha_source_coverage.format_source_coverage_report(unobserved)
    assert "configured providers with no health row are skipped/not observed" in unobserved_text
    assert "skipped/not observed providers: gdelt, project_blog_rss" in unobserved_text
    assert "provider coverage status: skipped_live_calls_disabled" in unobserved_text

    with tempfile.TemporaryDirectory() as tmp:
        ledger_path = Path(tmp) / "cryptopanic_request_ledger.jsonl"
        ledger_path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-06-15T12:00:00+00:00",
                    "status_code": 200,
                    "result_count": 1,
                    "quota_counted": True,
                    "currencies": "RUNE",
                    "normalized_request_key": "cryptopanic:RUNE",
                    "request_url_redacted": "https://cryptopanic.com/api/growth_weekly/v2/posts/?auth_token=<redacted>&currencies=RUNE",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        configured_report = event_provider_status.build_event_discovery_provider_status(
            _event_provider_status_cfg(
                EVENT_DISCOVERY_CRYPTOPANIC_LIVE=True,
                EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN="SECRET_TOKEN_SHOULD_NOT_RENDER",
            )
        )
        success_report = event_alpha_source_coverage.build_source_coverage_report(
            provider_status_report=configured_report,
            provider_health_rows={
                "cryptopanic:catalyst_search": {
                    "provider_key": "cryptopanic:catalyst_search",
                    "provider_service": "cryptopanic",
                    "provider_role": "catalyst_search",
                    "disabled_until": "2999-01-01T00:00:00+00:00",
                    "last_error_class": "HTTPError",
                }
            },
            evidence_acquisition_rows=[
                {
                    "source_pack": "security_shock_pack",
                    "status": "accepted_evidence_found",
                    "accepted_evidence": [{
                        "provider": "cryptopanic",
                        "reason_codes": ("cryptopanic_currency_tag_match",),
                    }],
                }
            ],
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep_cryptopanic_rehearsal",
            cryptopanic_request_ledger_path=ledger_path,
            now=datetime(2026, 6, 15, 13, tzinfo=timezone.utc),
        )
        success_text = event_alpha_source_coverage.format_source_coverage_report(success_report)
        assert success_report.cryptopanic_health_status == "healthy"
        assert success_report.cryptopanic_coverage_status == "observed_healthy"
        assert success_report.cryptopanic_successful_requests == 1
        assert success_report.cryptopanic_backoff_reconciled_after_success is True
        assert success_report.cryptopanic_recommendation == "no action; accepted CryptoPanic evidence is available"
        success_packs = {pack.source_pack: pack for pack in success_report.packs}
        success_security = success_packs["security_shock_pack"]
        assert "cryptopanic" in success_security.healthy_providers
        assert "cryptopanic" not in success_security.degraded_or_backoff_providers
        assert "cryptopanic:catalyst_search=healthy" in success_security.provider_role_statuses
        assert "configure CryptoPanic token" not in success_text
        assert "restore CryptoPanic token/news coverage" not in success_text
        source_report_path = Path(tmp) / "event_alpha_source_coverage.md"
        source_report_path.write_text(success_text, encoding="utf-8")
        doctor_success = event_alpha_artifact_doctor.diagnose_artifacts(
            evidence_acquisition_rows=[
                {
                    "source_pack": "security_shock_pack",
                    "status": "accepted_evidence_found",
                    "core_opportunity_id": "core:rune",
                    "accepted_evidence_count": 1,
                    "accepted_evidence": [{"provider": "cryptopanic"}],
                    "rejected_evidence_count": 0,
                    "rejected_evidence": [],
                }
            ],
            core_opportunity_rows=[],
            card_paths=[],
            source_coverage_report_path=source_report_path,
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep_cryptopanic_rehearsal",
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor_success.cryptopanic_success_with_backoff_status == 0
        assert doctor_success.cryptopanic_restore_token_recommendation_when_configured == 0
        assert doctor_success.evidence_count_mismatch == 0

    configured_cfg = _event_provider_status_cfg(
        EVENT_DISCOVERY_CRYPTOPANIC_LIVE=True,
        EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN="SECRET_TOKEN_SHOULD_NOT_RENDER",
    )
    configured_report = event_provider_status.build_event_discovery_provider_status(configured_cfg)
    with TemporaryDirectory() as tmp_ledger:
        ledger = Path(tmp_ledger) / "cryptopanic_request_ledger.jsonl"
        ledger.write_text(json.dumps({
            "timestamp": "2026-06-15T00:00:00+00:00",
            "plan": "growth_weekly",
            "request_url_redacted": "https://cryptopanic.test/api/growth_weekly/v2/posts/?auth_token=%3Credacted%3E&currencies=RUNE",
            "currencies": "RUNE",
            "status_code": 200,
            "result_count": 0,
            "error_class": "json_parse_error",
            "content_type": "text/html",
            "body_excerpt_redacted": "<html>Cloudflare</html>",
            "parse_error_message": "Expecting value",
            "quota_counted": True,
        }) + "\n", encoding="utf-8")
        parse_report = event_alpha_source_coverage.build_source_coverage_report(
            provider_status_report=configured_report,
            provider_health_rows={"cryptopanic:catalyst_search": {
                "provider_service": "cryptopanic",
                "provider_role": "catalyst_search",
                "last_error_class": "json_parse_error",
                "consecutive_failures": 1,
            }},
            evidence_acquisition_rows=[],
            core_opportunity_rows=[],
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep",
            cryptopanic_request_ledger_path=ledger,
            now=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )
        parse_text = event_alpha_source_coverage.format_source_coverage_report(parse_report)
        assert parse_report.cryptopanic_configured is True
        assert parse_report.cryptopanic_observed is True
        assert parse_report.cryptopanic_coverage_status == "observed_parse_error"
        assert "coverage status: observed_parse_error" in parse_text
        assert "inspect cryptopanic_request_ledger.jsonl body excerpt" in parse_text
        assert "configure CryptoPanic token/news coverage" not in parse_text

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "event_alpha_source_coverage.md"
        report_path.write_text(unobserved_text, encoding="utf-8")
        source_report_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "source-coverage-test",
                "profile": "notify_llm_deep",
                "artifact_namespace": "notify_llm_deep",
                "run_mode": "test",
            }],
            source_coverage_report_path=report_path,
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep",
            include_test_artifacts=True,
            strict=True,
        )
        assert source_report_doctor.source_coverage_report_missing == 0
        assert source_report_doctor.source_coverage_provider_status_unknown == 0
        assert source_report_doctor.source_coverage_provider_marked_healthy_without_observation == 0
        assert source_report_doctor.source_coverage_readiness_link_missing == 0
        bad_rank_path = Path(tmp) / "bad_rank_source_coverage.md"
        bad_rank_path.write_text(
            "Most useful next data source:\n"
            "- gdelt: broad context\n"
            "- coinalyze: derivatives/OI/funding\n",
            encoding="utf-8",
        )
        bad_rank_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "source-coverage-rank-test",
                "profile": "notify_llm_deep",
                "artifact_namespace": "notify_llm_deep",
                "run_mode": "test",
            }],
            source_coverage_report_path=bad_rank_path,
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep",
            include_test_artifacts=True,
            strict=True,
        )
        assert bad_rank_doctor.source_coverage_context_provider_ranked_above_lane_critical == 1

        parse_report_path = Path(tmp) / "event_alpha_source_coverage.md"
        parse_report_path.write_text(
            "CryptoPanic:\n- configured: true\n- observed this run: true\n- coverage status: observed_parse_error\n",
            encoding="utf-8",
        )
        (Path(tmp) / "cryptopanic_request_ledger.jsonl").write_text(
            "\n".join([
                json.dumps({
                    "timestamp": "2026-06-15T00:00:00+00:00",
                    "plan": "growth_weekly",
                    "request_url_redacted": "https://cryptopanic.test/api/growth_weekly/v2/posts/?auth_token=%3Credacted%3E&search=RUNE",
                    "currencies": "RUNE",
                }),
                json.dumps({
                    "timestamp": "2026-06-15T00:01:00+00:00",
                    "plan": "enterprise",
                    "request_url_redacted": "https://cryptopanic.test/api/enterprise/v2/posts/?auth_token=%3Credacted%3E&search=RUNE",
                    "currencies": "RUNE",
                }),
                json.dumps({
                    "timestamp": "2026-06-15T00:02:00+00:00",
                    "plan": "growth_weekly",
                    "request_url_redacted": "https://cryptopanic.test/api/growth_weekly/v2/posts/?auth_token=plain_test_token",
                    "currencies": "BAD",
                    "error_class": "json_parse_error",
                    "body_excerpt_redacted": "<html>bad</html>",
                }),
            ]) + "\n",
            encoding="utf-8",
        )
        cryptopanic_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            source_coverage_report_path=parse_report_path,
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep",
            include_test_artifacts=True,
            strict=True,
        )
        assert cryptopanic_doctor.cryptopanic_growth_unsupported_param_used == 1
        assert cryptopanic_doctor.cryptopanic_token_printed_or_unredacted == 1
        assert cryptopanic_doctor.cryptopanic_json_parse_errors == 1
        assert cryptopanic_doctor.cryptopanic_configured_but_unusable == 1

        missing_report_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "source-coverage-missing-test",
                "profile": "notify_llm_deep",
                "artifact_namespace": "notify_llm_deep",
                "run_mode": "test",
            }],
            source_coverage_report_path=Path(tmp) / "missing.md",
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep",
            include_test_artifacts=True,
        )
        assert missing_report_doctor.source_coverage_report_missing == 1
    assert any("degraded_provider_absence_marked_meaningful=1" in item for item in doctor.blockers)
