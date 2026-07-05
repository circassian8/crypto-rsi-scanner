"""Focused source-coverage package refactor tests."""

from __future__ import annotations

from datetime import datetime, timezone
from tempfile import TemporaryDirectory


def test_source_coverage_canonical_import_paths_resolve_same_objects():
    import crypto_rsi_scanner.event_alpha.radar.source_coverage as direct_source_coverage
    from crypto_rsi_scanner.event_alpha.radar import source_coverage as new_source_coverage

    assert direct_source_coverage.build_source_coverage_report is new_source_coverage.build_source_coverage_report
    assert direct_source_coverage.format_source_coverage_report is new_source_coverage.format_source_coverage_report
    assert direct_source_coverage.LIVE_PROVIDER_READINESS_MD == new_source_coverage.LIVE_PROVIDER_READINESS_MD
    assert direct_source_coverage.LIVE_PROVIDER_READINESS_JSON == new_source_coverage.LIVE_PROVIDER_READINESS_JSON


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

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})

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
    assert categories[-1]["category"] == "Context/news"
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
    assert unobserved_proxy.provider_coverage_status == "unknown"
    assert "gdelt:not_observed=unknown" in unobserved_proxy.provider_role_statuses
    unobserved_text = event_alpha_source_coverage.format_source_coverage_report(unobserved)
    assert "configured providers with no health row are unknown/not observed" in unobserved_text
    assert "unknown/not observed providers: gdelt, project_blog_rss" in unobserved_text
    assert "provider coverage status: unknown" in unobserved_text

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
        assert source_report_doctor.source_coverage_provider_status_unknown > 0
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


def test_event_catalyst_search_cryptopanic_uses_symbol_and_coin_currency_filters():
    import json
    from datetime import datetime, timezone
    from urllib.parse import parse_qs, urlparse
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search

    class FakeResponse:
        status = 200

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    seen = {}

    def fake_opener(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return FakeResponse({"results": []})

    provider = event_catalyst_search.CryptoPanicCatalystSearchProvider(
        live_enabled=True,
        api_token="token123",
        base_url="https://cryptopanic.test/api/growth_weekly/v2",
        opener=fake_opener,
        min_seconds_between_requests=0,
    )
    result = provider.search(
        (
            event_catalyst_search.SearchQuery(
                anomaly_raw_id="hyp:rune",
                query="RUNE exploit official update",
                symbol="RUNE",
                coin_id="thorchain",
                aliases=("RUNE", "thorchain"),
                rank=1,
            ),
        ),
        max_results_per_query=1,
        now=datetime(2026, 6, 15, 12, tzinfo=timezone.utc),
    )

    params = parse_qs(urlparse(seen["url"]).query)
    assert urlparse(seen["url"]).path == "/api/growth_weekly/v2/posts/"
    assert params["currencies"] == ["RUNE"]
    assert params["kind"] == ["news"]
    assert params["public"] == ["true"]
    assert "search" not in params
    assert "size" not in params
    assert "last_pull" not in params
    assert "with_content" not in params
    assert seen["timeout"] == 10.0
    assert result.query_count == 1
    assert result.result_count == 0


def test_event_catalyst_search_scaffold_attaches_evidence_without_bypassing_discovery():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.anomaly_scanner as event_anomaly_scanner
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.market_enrichment as event_market_enrichment
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    rows = [{
        "id": "pump-protocol",
        "symbol": "pump",
        "name": "Pump Protocol",
        "current_price": 1.4,
        "market_cap": 100000000.0,
        "total_volume": 60000000.0,
        "price_change_percentage_24h_in_currency": 45.0,
        "price_change_percentage_7d_in_currency": 120.0,
        "volume_zscore_24h": 4.5,
    }]
    anomaly = event_anomaly_scanner.discover_market_anomalies(
        rows,
        cfg=event_anomaly_scanner.EventAnomalyScannerConfig(
            enabled=True,
            min_return_24h=0.30,
            min_volume_mcap=0.25,
            min_volume_zscore=3.0,
        ),
        now=now,
    )[0]
    queries = event_catalyst_search.generate_search_queries_for_anomaly(anomaly)
    assert "PUMP crypto why up" in queries
    assert "PUMP Binance listing" in queries
    assert "PUMP SpaceX exposure" in queries

    asset = DiscoveredAsset(
        coin_id="pump-protocol",
        symbol="PUMP",
        name="Pump Protocol",
        aliases=("pump protocol", "pump"),
    )
    market_by_asset = event_market_enrichment.market_snapshots_from_rows(rows, now=now)
    no_evidence_rows = event_catalyst_search.attach_search_results_to_anomaly(anomaly, ())
    no_evidence_result = event_discovery.run_discovery(
        no_evidence_rows,
        [asset],
        now=now,
        market_by_asset=market_by_asset,
    )
    no_evidence_alert = event_alerts.build_event_alert_candidates(no_evidence_result, now=now)[0]
    assert no_evidence_alert.playbook_type == event_playbooks.EventPlaybookType.MARKET_ANOMALY_UNKNOWN.value
    assert no_evidence_alert.tier in {
        event_alerts.EventAlertTier.STORE_ONLY,
        event_alerts.EventAlertTier.RADAR_DIGEST,
    }
    assert no_evidence_alert.tier != event_alerts.EventAlertTier.WATCHLIST

    listing_raw = RawDiscoveredEvent(
        raw_id="pump-binance-listing",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pump-binance-listing",
        title="Binance will list Pump Protocol (PUMP)",
        body="Binance will list Pump Protocol spot trading pairs today.",
        raw_json={
            "event": {
                "event_id": "pump-binance-listing",
                "event_name": "Binance will list Pump Protocol (PUMP)",
                "event_type": "exchange_listing",
                "event_time": "2026-06-18T20:00:00Z",
                "event_time_confidence": 0.95,
                "external_asset": None,
                "confidence": 0.90,
                "description": "Binance will list Pump Protocol spot trading pairs today.",
            }
        },
        source_confidence=0.90,
        content_hash="pump-binance-listing",
    )
    attached_rows = event_catalyst_search.attach_search_results_to_anomaly(anomaly, (listing_raw,))
    assert attached_rows[1].raw_json["market_anomaly_catalyst_search"]["role"] == "attached_source_evidence"
    with_evidence_result = event_discovery.run_discovery(
        attached_rows,
        [asset],
        now=now,
        market_by_asset=market_by_asset,
    )
    listing_alert = next(
        alert for alert in event_alerts.build_event_alert_candidates(with_evidence_result, now=now)
        if alert.discovery_candidate.event.event_id == "pump-binance-listing"
    )
    assert listing_alert.playbook_type == event_playbooks.EventPlaybookType.LISTING_VOLATILITY.value
    assert listing_alert.tier in {
        event_alerts.EventAlertTier.WATCHLIST,
        event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH,
    }
    assert listing_alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE


def test_event_catalyst_search_skip_reasons_flow_to_ledger_and_brief():
    import tempfile
    from dataclasses import replace
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.artifacts.run_ledger as event_alpha_run_ledger
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def anomaly(raw_id="market_anomaly:pump:2026-06-18", score=90.0, symbol="PUMP"):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="market_anomaly",
            fetched_at=now,
            published_at=now,
            source_url=None,
            title=f"{symbol} market anomaly",
            body=None,
            raw_json={
                "symbol": symbol,
                "market": {"symbol": symbol, "coin_id": "pump-protocol", "name": "Pump Protocol"},
                "anomaly": {"score": score, "return_24h": 0.45},
            },
            source_confidence=0.70,
            content_hash=raw_id,
        )

    low = anomaly(raw_id="market_anomaly:low:2026-06-18", score=25.0, symbol="LOW")
    cfg = event_catalyst_search.EventCatalystSearchConfig(
        enabled=True,
        min_anomaly_score=60,
        max_queries_per_anomaly=4,
    )
    low_result = event_catalyst_search.run_catalyst_search(
        [low],
        event_catalyst_search.FixtureCatalystSearchProvider({}),
        cfg=cfg,
        now=now,
    )
    assert low_result.queries == ()
    assert low_result.skip_reasons["no_anomalies_over_threshold"] == 1

    high = anomaly()

    def loader(observed, raw_event_transform):
        raw_events = (high,)
        if raw_event_transform:
            raw_events = tuple(raw_event_transform(raw_events))
        return event_discovery.run_discovery(raw_events, [], now=observed)

    no_provider = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=loader,
        now=now,
        catalyst_search_provider=None,
        catalyst_search_cfg=cfg,
        refresh_watchlist=False,
        route=False,
    )
    assert no_provider.catalyst_search_skip_reasons["provider_unavailable"] == 1
    assert no_provider.catalyst_queries == 0

    class BackoffProvider:
        name = "backoff"

        def search(self, queries, *, max_results_per_query, now=None):
            queries = tuple(queries)
            return event_catalyst_search.CatalystSearchRunResult(
                provider=self.name,
                queries=queries,
                warnings=("provider in backoff until later",),
                query_count=len(queries),
            )

    backoff = event_catalyst_search.run_catalyst_search([high], BackoffProvider(), cfg=cfg, now=now)
    assert backoff.queries
    assert backoff.skip_reasons["provider_backoff"] == 1

    with tempfile.TemporaryDirectory() as tmp:
        row = event_alpha_run_ledger.append_run_record(
            replace(
                no_provider,
                cryptopanic_configured=True,
                cryptopanic_attempted=True,
                cryptopanic_requests_used=2,
                cryptopanic_results=3,
                cryptopanic_accepted_evidence=1,
                cryptopanic_rejected_evidence=2,
                cryptopanic_provider_status="healthy",
            ),
            cfg=event_alpha_run_ledger.EventAlphaRunLedgerConfig(Path(tmp) / "runs.jsonl"),
            profile="fixture",
            started_at=now,
            finished_at=now,
            with_llm=False,
            send_requested=False,
        )
        assert row["catalyst_search_skip_reasons"]["provider_unavailable"] == 1
        assert row["cryptopanic_configured"] is True
        assert row["cryptopanic_attempted"] is True
        assert row["cryptopanic_requests_used"] == 2
        assert row["cryptopanic_results"] == 3
        assert row["cryptopanic_accepted_evidence"] == 1
        assert row["cryptopanic_rejected_evidence"] == 2
        assert row["cryptopanic_provider_status"] == "healthy"
        runs_report = event_alpha_run_ledger.format_run_ledger_report(
            event_alpha_run_ledger.EventAlphaRunLedgerReadResult(
                path=Path(tmp) / "runs.jsonl",
                rows_read=1,
                rows=[row],
            )
        )
        assert "catalyst_search_skip_reasons: provider_unavailable=1" in runs_report
        assert "cryptopanic configured=true attempted=true requests=2 results=3 accepted=1 rejected=2 status=healthy skip=none" in runs_report
        brief = event_alpha_daily_brief.build_daily_brief(
            run_rows=[row],
            include_test_artifacts=True,
            include_api_artifacts=True,
        )
        assert "## Catalyst Search Skip Reasons" in brief
        assert "- provider_unavailable: 1" in brief


def test_event_catalyst_search_proxy_evidence_still_requires_deterministic_validation():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    anomaly = RawDiscoveredEvent(
        raw_id="market_anomaly:pumpx:2026-06-18",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="PUMPX market anomaly: 24h return 95%",
        body="No dated external catalyst has been validated.",
        raw_json={
            "event": {
                "event_id": "market_anomaly:pumpx:2026-06-18",
                "event_name": "PUMPX market anomaly",
                "event_type": "market_anomaly",
                "event_time": None,
                "event_time_confidence": 0.0,
                "confidence": 0.60,
                "description": "No dated external catalyst has been validated.",
            },
            "market": {"symbol": "PUMPX", "coin_id": "pumpx", "return_24h": 0.95, "volume_zscore_24h": 5.0},
            "anomaly": {"score": 95, "reasons": ["24h return 95%"]},
        },
        source_confidence=0.55,
        content_hash="anomaly-pumpx",
    )
    proxy_raw = RawDiscoveredEvent(
        raw_id="pumpx-openai-proxy",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pumpx-openai",
        title="PumpX launches OpenAI pre-IPO exposure market",
        body="PumpX token holders can use the PUMPX venue for OpenAI pre-IPO exposure.",
        raw_json={
            "event": {
                "event_id": "pumpx-openai-proxy",
                "event_name": "PumpX launches OpenAI pre-IPO exposure market",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-20T13:30:00Z",
                "event_time_confidence": 0.90,
                "external_asset": "OpenAI",
                "confidence": 0.90,
                "description": "PumpX token holders can use the PUMPX venue for OpenAI pre-IPO exposure.",
            }
        },
        source_confidence=0.90,
        content_hash="pumpx-openai-proxy",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider({"PUMPX OpenAI exposure": (proxy_raw,)})
    cfg = event_catalyst_search.EventCatalystSearchConfig(
        enabled=True,
        max_anomalies=1,
        max_queries_per_anomaly=6,
        max_results_per_query=1,
        min_anomaly_score=60,
    )

    def loader_without_asset(observed, raw_event_transform):
        raw_events = tuple(raw_event_transform((anomaly,))) if raw_event_transform else (anomaly,)
        return event_discovery.run_discovery(raw_events, [], now=observed)

    no_asset = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=loader_without_asset,
        now=now,
        catalyst_search_provider=provider,
        catalyst_search_cfg=cfg,
        refresh_watchlist=False,
        route=False,
    )
    assert no_asset.candidates == 0

    asset = DiscoveredAsset(coin_id="pumpx", symbol="PUMPX", name="PumpX", aliases=("pumpx",))

    def loader_with_asset(observed, raw_event_transform):
        raw_events = tuple(raw_event_transform((anomaly,))) if raw_event_transform else (anomaly,)
        return event_discovery.run_discovery(raw_events, [asset], now=observed)

    with_asset = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=loader_with_asset,
        alert_cfg=event_alerts.EventAlertConfig(),
        now=now,
        catalyst_search_provider=provider,
        catalyst_search_cfg=cfg,
        refresh_watchlist=False,
        route=False,
    )
    proxy_alert = next(
        alert for alert in with_asset.alerts
        if alert.discovery_candidate.event.event_id == "pumpx-openai-proxy"
    )
    assert proxy_alert.playbook_type in {
        event_playbooks.EventPlaybookType.PROXY_FADE.value,
        event_playbooks.EventPlaybookType.AI_IPO_PROXY.value,
        event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
    }
    assert proxy_alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE


def test_event_catalyst_search_requires_identity_before_attaching_catalyst_terms():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    anomaly = RawDiscoveredEvent(
        raw_id="market_anomaly:pump:2026-06-18",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="PUMP market anomaly",
        body="No catalyst validated.",
        raw_json={
            "market": {
                "symbol": "PUMP",
                "coin_id": "pump-fun",
                "name": "Pump.fun",
                "aliases": ["Pump.fun", "Pump Protocol"],
            },
            "anomaly": {"score": 95},
        },
        source_confidence=0.55,
        content_hash="anomaly-pump",
    )
    unrelated = RawDiscoveredEvent(
        raw_id="other-listing",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/other",
        title="Binance will list Other Protocol (OTHER)",
        body="Binance listing catalyst for Other only.",
        raw_json={"event": {"event_type": "exchange_listing", "event_time": "2026-06-18T20:00:00Z"}},
        source_confidence=0.95,
        content_hash="other-listing",
    )
    alias = RawDiscoveredEvent(
        raw_id="pump-alias",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/pump",
        title="Pump.fun confirms PUMPUSDT perp listing",
        body="Pump.fun will launch PUMPUSDT futures trading.",
        raw_json={"event": {"event_type": "perp_listing", "event_time": "2026-06-18T20:00:00Z"}},
        source_confidence=0.95,
        content_hash="pump-alias",
    )
    query = event_catalyst_search.generate_search_query_objects_for_anomaly(anomaly, max_queries=20)[0]
    unrelated_score = event_catalyst_search.score_search_result(unrelated, query, anomaly, now=now)
    alias_score = event_catalyst_search.score_search_result(alias, query, anomaly, now=now)
    assert "identity_missing_cap" in unrelated_score.reason_codes
    assert unrelated_score.score < 50
    assert any(
        reason in alias_score.reason_codes
        for reason in ("identity_match_alias", "identity_match_pair", "identity_match_project")
    )
    assert alias_score.score >= 50


def test_event_catalyst_search_rejects_common_word_symbol_without_strong_identity():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    anomaly = RawDiscoveredEvent(
        raw_id="market_anomaly:hype:2026-06-18",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="HYPE market anomaly",
        body="No catalyst validated.",
        raw_json={"market": {"symbol": "HYPE", "coin_id": "hyperliquid", "name": "Hyperliquid"}, "anomaly": {"score": 95}},
        source_confidence=0.55,
        content_hash="anomaly-hype",
    )
    generic = RawDiscoveredEvent(
        raw_id="ipo-hype",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/hype",
        title="IPO hype builds around Stripe",
        body="A story about IPO hype and prediction markets for private companies.",
        raw_json={},
        source_confidence=0.90,
        content_hash="ipo-hype",
    )
    query = event_catalyst_search.generate_search_query_objects_for_anomaly(anomaly, max_queries=1)[0]
    score = event_catalyst_search.score_search_result(generic, query, anomaly, now=now)
    assert "common_word_identity_rejected" in score.reason_codes
    assert score.score < 50


def test_event_catalyst_search_identity_can_come_from_resolver_validated_llm_extraction():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="stealth-source",
        provider="fixture_search_result",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/stealth",
        title="New protocol launches OpenAI pre-IPO exposure",
        body="A venue launches OpenAI pre-IPO exposure.",
        raw_json={
            "llm_extraction": {
                "crypto_asset_mentions": [
                    {
                        "name": "Stealth Alpha",
                        "symbol": "STEALTH",
                        "coin_id": "stealth-alpha",
                        "confidence": 0.91,
                        "resolver_validated": True,
                        "mention_type": "project_or_token",
                    }
                ]
            }
        },
        source_confidence=0.85,
        content_hash="stealth-source",
    )
    query = event_catalyst_search.SearchQuery(
        anomaly_raw_id="market_anomaly:stealth-alpha:2026-06-18",
        query="STEALTH OpenAI exposure",
        symbol="STEALTH",
        rank=1,
        coin_id="stealth-alpha",
    )
    assert event_catalyst_search.result_mentions_anomaly_identity(raw, query, None) is True


def test_event_catalyst_search_identity_field_safety_rejects_url_and_source_noise():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, *, title="", body="", source_url=None, provider="fixture_search_result", raw_json=None):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider=provider,
            fetched_at=now,
            published_at=now,
            source_url=source_url,
            title=title,
            body=body,
            raw_json=raw_json or {},
            source_confidence=0.85,
            content_hash=raw_id,
        )

    pump_query = event_catalyst_search.SearchQuery(
        anomaly_raw_id="market_anomaly:pump:2026-06-18",
        query="PUMP Binance listing",
        symbol="PUMP",
        rank=1,
        coin_id="pump-token",
    )
    url_only = raw(
        "url-only",
        title="Exchange listing roundup",
        body="A listing roundup mentions other tokens.",
        source_url="https://example.test/search?q=PUMPUSDT",
    )
    assert event_catalyst_search.result_mentions_anomaly_identity(url_only, pump_query, None) is False
    score = event_catalyst_search.score_search_result(url_only, pump_query, now=now)
    assert "identity_url_only_rejected" in score.reason_codes

    body_pair = raw(
        "body-pair",
        title="Binance lists a new perp",
        body="Binance confirms PUMPUSDT perpetual trading starts today.",
        source_url="https://example.test/news/listing",
    )
    assert event_catalyst_search.result_mentions_anomaly_identity(body_pair, pump_query, None) is True
    assert "identity_match_pair" in event_catalyst_search.score_search_result(body_pair, pump_query, now=now).reason_codes

    btc_query = event_catalyst_search.SearchQuery(
        anomaly_raw_id="market_anomaly:bitcoin:2026-06-18",
        query="BTC catalyst",
        symbol="BTC",
        rank=1,
        coin_id="bitcoin",
    )
    publisher = raw(
        "publisher",
        title="SpaceX pre-IPO markets expand",
        body="The article is about SpaceX exposure.",
        source_url="https://bitcoinworld.example/news/spacex",
        raw_json={"source_origin": "Bitcoin World"},
    )
    assert event_catalyst_search.result_mentions_anomaly_identity(publisher, btc_query, None) is False
    assert "identity_source_origin_rejected" in event_catalyst_search.score_search_result(publisher, btc_query, now=now).reason_codes

    address = "0x1234567890abcdef1234567890abcdef12345678"
    contract_query = event_catalyst_search.SearchQuery(
        anomaly_raw_id="market_anomaly:contract-token:2026-06-18",
        query="CONTRACT catalyst",
        symbol="CONTRACT",
        rank=1,
        contract_addresses=(address,),
    )
    path_contract = raw(
        "contract-path",
        title="Protocol update",
        body="Contract details published.",
        source_url=f"https://etherscan.io/token/{address}",
    )
    assert event_catalyst_search.result_mentions_anomaly_identity(path_contract, contract_query, None) is True

    query_contract = raw(
        "contract-query",
        title="Protocol update",
        body="Contract details published.",
        source_url=f"https://example.test/search?contract={address}",
    )
    assert event_catalyst_search.result_mentions_anomaly_identity(query_contract, contract_query, None) is False
    assert "identity_url_only_rejected" in event_catalyst_search.score_search_result(query_contract, contract_query, now=now).reason_codes


def test_event_catalyst_search_provider_cache_fetches_broad_sources_once():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    article = {
        "id": "pump-rss",
        "title": "Pump.fun confirms PUMPUSDT perp listing",
        "body": "Pump.fun will launch PUMPUSDT futures trading.",
        "published_at": now.isoformat(),
        "fetched_at": now.isoformat(),
        "url": "https://example.test/pump-rss",
        "source_confidence": 0.90,
    }
    queries = tuple(
        event_catalyst_search.SearchQuery(
            anomaly_raw_id=f"market_anomaly:pump:{idx}",
            query=f"PUMP catalyst {idx}",
            symbol="PUMP",
            rank=idx,
            coin_id="pump-fun",
            project_name="Pump.fun",
            aliases=("Pump.fun",),
        )
        for idx in range(10)
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rss.json"
        path.write_text(json.dumps({"articles": [article]}), encoding="utf-8")
        provider = event_catalyst_search.ProjectRssCatalystSearchProvider(path=path)
        result = provider.search(queries, max_results_per_query=1, now=now)
        assert result.provider_fetch_count == 1
        assert result.provider_cache_misses == 1
        assert result.provider_cache_hits == 9
        assert result.query_count == 10


def test_event_source_enrichment_extracts_and_reuses_cache():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
    import crypto_rsi_scanner.event_alpha.radar.source_enrichment as event_source_enrichment
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="article",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://news.example/article",
        title="SpaceX pre-IPO exposure",
        body="Short RSS summary.",
        raw_json={},
        source_confidence=0.9,
        content_hash="article",
    )
    html = """
    <html><head><style>.x{}</style><script>ignore()</script></head>
    <body><nav>Home Markets Prices News Learn Newsletter</nav>
    <div>BTC $104000 +2.1% ETH $2500 -1.0% SOL $150 +4.4%</div>
    <article><h1>SpaceX pre-IPO exposure</h1>
    <p>Velvet Capital is named in the full article, but not the RSS summary.</p>
    <p>Hyperliquid HYPE token traders are watching the proxy venue.</p>
    <p>The article explains the candidate asset, the external SpaceX catalyst,
    and the direct proxy mechanism clearly enough to pass source-quality gating.</p>
    <p>This extra body copy keeps the synthetic fixture above the thin article
    threshold while preserving the expected article text.</p></article></body></html>
    """
    calls = {"count": 0}

    def fetch(url, timeout):
        calls["count"] += 1
        assert url == "https://news.example/article"
        assert timeout == 2
        return html

    with tempfile.TemporaryDirectory() as tmp:
        cfg = event_source_enrichment.EventSourceEnrichmentConfig(
            enabled=True,
            cache_dir=Path(tmp),
            timeout_seconds=2,
        )
        first = event_source_enrichment.enrich_source_text(raw, cfg=cfg, fetch_fn=fetch)
        second = event_source_enrichment.enrich_source_text(raw, cfg=cfg, fetch_fn=lambda *_: (_ for _ in ()).throw(RuntimeError("should not fetch")))
        assert first.fetched is True
        assert "Velvet Capital is named" in first.enriched_text
        assert "Hyperliquid HYPE token traders" in first.enriched_text
        assert "Home Markets Prices" not in first.enriched_text
        assert "BTC $104000" not in first.enriched_text
        assert second.used_cache is True
        assert "Velvet Capital is named" in second.enriched_text
        assert "Hyperliquid HYPE token traders" in second.enriched_text
        assert calls["count"] == 1
        refreshed = event_source_enrichment.enrich_source_text(
            raw,
            cfg=event_source_enrichment.EventSourceEnrichmentConfig(
                enabled=True,
                cache_dir=Path(tmp),
                timeout_seconds=2,
                cleaner_version="source_enrichment_cleaner_v999",
            ),
            fetch_fn=fetch,
        )
        assert refreshed.fetched is True
        assert calls["count"] == 2
        annotated = event_source_enrichment.annotate_raw_event_with_enrichment(first)
        packet = event_llm_extractor.build_raw_event_packet(annotated)
        assert "Velvet Capital is named" in packet["body"]

    failed = event_source_enrichment.enrich_source_text(
        raw,
        cfg=event_source_enrichment.EventSourceEnrichmentConfig(enabled=True),
        fetch_fn=lambda *_: (_ for _ in ()).throw(RuntimeError("network down")),
    )
    assert failed.warning == "source enrichment failed: RuntimeError"
    assert "Short RSS summary" in failed.enriched_text


def test_event_source_enrichment_uses_fixture_text_for_example_test_urls():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.source_enrichment as event_source_enrichment
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="fixture_article",
        provider="fixture_rss",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/article?fixture=VELVET",
        title="SpaceX pre-IPO exposure",
        body="Fixture body mentions Velvet Capital and SpaceX pre-IPO exposure.",
        raw_json={},
        source_confidence=0.9,
        content_hash="fixture_article",
    )

    result = event_source_enrichment.enrich_source_text(
        raw,
        cfg=event_source_enrichment.EventSourceEnrichmentConfig(enabled=True),
        fetch_fn=lambda *_: (_ for _ in ()).throw(RuntimeError("should not fetch fixture URL")),
    )

    assert result.status == "fixture_text_used"
    assert result.fetched is False
    assert "Velvet Capital" in result.enriched_text
    annotated = event_source_enrichment.annotate_raw_event_with_enrichment(result)
    assert annotated.raw_json["source_enrichment"]["status"] == "fixture_text_used"


def test_event_alpha_pipeline_source_enrichment_runs_before_llm_extraction():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.llm.extractor as event_llm_extractor
    import crypto_rsi_scanner.event_alpha.radar.source_enrichment as event_source_enrichment
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="source-enrich-before-llm",
        provider="rss",
        fetched_at=now,
        published_at=now,
        source_url="https://news.example/enrich",
        title="SpaceX pre-IPO exposure opens",
        body="Short summary without the asset name.",
        raw_json={},
        source_confidence=0.90,
        content_hash="source-enrich-before-llm",
    )
    seen = {"body": ""}

    class Provider:
        name = "fixture"

        def extract_raw_event(self, packet):
            seen["body"] = packet["body"]
            return LLMProviderResult(raw={
                "confidence": 0.90,
                "external_catalysts": [{
                    "name": "SpaceX",
                    "catalyst_type": "ipo_proxy",
                    "event_time": None,
                    "event_time_confidence": 0.0,
                    "confidence": 0.90,
                    "evidence_quotes": [{"text": "SpaceX pre-IPO exposure", "source_field": "body", "supports": "external catalyst"}],
                }],
                "crypto_asset_mentions": [{
                    "name": "Velvet Capital",
                    "symbol": "VELVET",
                    "coin_id": "velvet",
                    "contract_address": None,
                    "mention_type": "project_or_token",
                    "confidence": 0.90,
                    "evidence_quotes": [{"text": "Velvet Capital users", "source_field": "body", "supports": "asset mention"}],
                }],
                "false_positive_terms": [],
                "event_date_hints": [],
                "suggested_followup_queries": [],
                "warnings": [],
            })

    def loader(observed, raw_event_transform):
        transformed = tuple(raw_event_transform((raw,))) if raw_event_transform else (raw,)
        return EventDiscoveryResult(
            raw_events=transformed,
            normalized_events=(),
            links=(),
            classifications=(),
            candidates=(),
            warnings=(),
        )

    pipe = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=loader,
        now=now,
        with_llm=True,
        extraction_provider=Provider(),
        extraction_cfg=event_llm_extractor.EventLLMExtractorConfig(mode="shadow", provider="fixture"),
        source_enrichment_cfg=event_source_enrichment.EventSourceEnrichmentConfig(
            enabled=True,
            max_chars=1000,
            min_source_confidence=0.50,
        ),
        source_enrichment_fetch_fn=lambda url, timeout: (
            "<html><body><article>"
            "Velvet Capital users can trade SpaceX pre-IPO exposure through a tokenized venue. "
            "The source names Velvet Capital, the SpaceX pre-IPO catalyst, and the direct proxy mechanism. "
            "This additional paragraph keeps the fixture above the thin-page threshold while preserving "
            "the exact quote used by the offline LLM extraction fixture."
            "</article></body></html>"
        ),
        refresh_watchlist=False,
        route=False,
    )
    assert pipe.extractions == 1
    assert "Velvet Capital users" in seen["body"]
    assert "source enrichment: selected=1 fetched=1 cache_hits=0" in "; ".join(pipe.warnings)


def test_event_source_reliability_report_recommendations():
    import crypto_rsi_scanner.event_alpha.providers.source_reliability as event_source_reliability

    alerts = [
        {"alert_key": "a", "source_provider": "rss", "primary_horizon_return": 0.12, "mfe_mae_ratio": 1.5},
        {"alert_key": "b", "source_provider": "rss", "primary_horizon_return": 0.05, "mfe_mae_ratio": 1.2},
        {"alert_key": "c", "source_provider": "bad", "primary_horizon_return": -0.02, "mfe_mae_ratio": 0.6},
        {"alert_key": "d", "source_provider": "bad", "primary_horizon_return": -0.03, "mfe_mae_ratio": 0.5},
    ]
    feedback = [
        {"key": "a", "label": "useful"},
        {"key": "b", "label": "useful"},
        {"key": "c", "label": "junk"},
        {"key": "d", "label": "junk"},
    ]
    missed = [{"failure_stage": "no_source_event"}, {"failure_stage": "no_source_event"}]
    report = event_source_reliability.format_source_reliability_report(alerts, feedback_rows=feedback, missed_rows=missed)
    assert "positive prior for rss" in report
    assert "tighten or demote bad" in report
    assert "coverage warning" in report


def test_event_source_registry_v2_provider_semantics():
    import crypto_rsi_scanner.event_alpha.providers.source_registry as event_source_registry

    polymarket_context = event_source_registry.assess_source(
        {"provider": "polymarket", "title": "SpaceX IPO market opens"},
        symbol="VELVET",
        coin_id="velvet",
    )
    assert polymarket_context.source_class == "prediction_market"
    assert polymarket_context.source_mission == "external_context"
    assert polymarket_context.can_validate_token_identity is False
    assert "external_context" in polymarket_context.can_prove
    assert "impact_path_validation" in polymarket_context.cannot_prove
    assert polymarket_context.evidence_absence_is_meaningful is False
    assert "prediction_market_external_context_only" in polymarket_context.reason_codes

    polymarket_named = event_source_registry.assess_source(
        {"provider": "polymarket", "title": "VELVET market for SpaceX exposure"},
        symbol="VELVET",
        coin_id="velvet",
    )
    assert polymarket_named.can_validate_token_identity is True
    assert "prediction_market_token_named_context" in polymarket_named.reason_codes

    gdelt_degraded = event_source_registry.assess_source(
        {"provider": "gdelt", "title": "Broad policy article mentions crypto"},
        symbol="BTC",
        coin_id="bitcoin",
        provider_coverage_status="degraded",
    )
    assert gdelt_degraded.source_class == "broad_news"
    assert gdelt_degraded.evidence_absence_is_meaningful is False
    assert gdelt_degraded.source_coverage_gap_reason == "provider_coverage_degraded:gdelt"
    assert "provider_coverage_degraded" in gdelt_degraded.warnings

    cryptopanic = event_source_registry.assess_source(
        {
            "provider": "cryptopanic",
            "title": "RUNE exploit update is important",
            "raw_json": {
                "currency_tags": ("RUNE",),
                "kind": "important",
            },
        },
        symbol="RUNE",
        coin_id="thorchain",
    )
    assert cryptopanic.source_class == "cryptopanic_tagged"
    assert cryptopanic.cryptopanic_currency_tag_match is True
    assert cryptopanic.narrative_heat is True
    assert "cryptopanic_currency_tag_match" in cryptopanic.reason_codes
    cryptopanic_mismatch = event_source_registry.assess_source(
        {
            "provider": "cryptopanic",
            "title": "Bullish market heat mentions RUNE",
            "currency_tags": ("BTC",),
            "kind": "hot",
        },
        symbol="RUNE",
        coin_id="thorchain",
    )
    assert cryptopanic_mismatch.source_class == "cryptopanic_tagged"
    assert cryptopanic_mismatch.cryptopanic_currency_tag_match is False
    assert cryptopanic_mismatch.can_validate_token_identity is False
    assert cryptopanic_mismatch.can_validate_impact_path is False
    assert "cryptopanic_narrative_heat_without_matching_tag" in cryptopanic_mismatch.warnings
    cryptopanic_contract = event_source_registry.source_contract_metadata(
        {"provider": "cryptopanic", "raw_json": {"currency_tags": ("RUNE",)}},
        evidence_rows=(
            {
                "source_can_prove": ("token_identity_validation", "impact_path_validation"),
                "source_cannot_prove": ("official_confirmation",),
                "source_useful_playbooks": ("security_or_regulatory_shock",),
            },
        ),
        symbol="RUNE",
        coin_id="thorchain",
    )
    assert "impact_path_validation" in cryptopanic_contract["source_can_prove"]
    assert "official_confirmation" in cryptopanic_contract["source_cannot_prove"]
    assert cryptopanic_contract["source_useful_playbooks"] == ("security_or_regulatory_shock",)

    exchange = event_source_registry.assess_source(
        {"provider": "binance_announcements", "title": "Binance Will List TEST"},
        symbol="TEST",
        coin_id="test-token",
    )
    assert exchange.source_class == "official_exchange"
    assert exchange.can_validate_token_identity is True
    assert exchange.can_validate_catalyst is True
    assert "official_confirmation" in exchange.can_prove
    assert "listing_volatility" in exchange.useful_playbooks

    market_data = event_source_registry.assess_source(
        {"provider": "coingecko_market_data", "title": "RUNE price snapshot"},
        symbol="RUNE",
        coin_id="thorchain",
    )
    assert market_data.source_class == "market_data"
    assert market_data.source_mission == "market_confirmation"
    assert "market_confirmation" in market_data.can_prove
    assert "impact_path_validation" in market_data.cannot_prove
    defillama = event_source_registry.assess_source(
        {"provider": "defillama", "title": "AAVE TVL and protocol fees snapshot"},
        symbol="AAVE",
        coin_id="aave",
    )
    assert defillama.source_class == "market_data"
    assert "market_confirmation" in defillama.can_prove
    assert "impact_path_validation" in defillama.cannot_prove
    geckoterminal = event_source_registry.assess_source(
        {"provider": "geckoterminal", "title": "VELVET DEX liquidity and pool volume snapshot"},
        symbol="VELVET",
        coin_id="velvet",
    )
    assert geckoterminal.source_class == "market_data"
    assert geckoterminal.source_mission == "market_confirmation"
    assert "market_confirmation" in geckoterminal.can_prove

    seo = event_source_registry.assess_source(
        {"provider": "rss", "title": "Best crypto to buy price prediction market recap"},
        symbol="HYPE",
        coin_id="hyperliquid",
    )
    assert seo.source_class in {"seo_or_affiliate", "market_recap"}
    assert seo.can_validate_token_identity is False
    assert "diagnostic_only_low_quality_source" in seo.warnings


def test_event_source_packs_and_feed_coverage_semantics():
    import crypto_rsi_scanner.event_alpha.providers.source_packs as event_source_packs
    import crypto_rsi_scanner.event_alpha.providers.source_registry as event_source_registry

    names = set(event_source_packs.source_pack_names())
    assert {
        "listing_liquidity_pack",
        "perp_listing_squeeze_pack",
        "unlock_supply_pack",
        "project_event_pack",
        "proxy_preipo_rwa_pack",
        "ai_ipo_proxy_pack",
        "security_shock_pack",
        "fan_sports_pack",
        "political_meme_pack",
        "strategic_investment_pack",
        "protocol_business_event_pack",
        "market_anomaly_pack",
    }.issubset(names)

    listing = event_source_packs.source_pack_for_playbook("listing_volatility")
    assert listing.name == "listing_liquidity_pack"
    assert "official_exchange" in listing.preferred_source_classes
    assert "cryptopanic_tagged" in listing.preferred_source_classes
    assert "official_exchange_source" in listing.sufficient_for_validated_digest
    assert "coinalyze" in listing.preferred_providers

    proxy = event_source_packs.source_pack_for_playbook("proxy_attention", impact_path_type="venue_value_capture")
    assert proxy.name == "proxy_preipo_rwa_pack"
    assert "prediction_market" in proxy.context_only_sources
    assert "official_project" in proxy.impact_path_validating_sources
    assert "geckoterminal" in proxy.preferred_providers
    assert "liquidity_sanity" in proxy.required_for_high_priority

    strategic = event_source_packs.source_pack_for_playbook(
        "strategic_investment",
        impact_path_type="strategic_investment_or_valuation",
    )
    assert strategic.name == "strategic_investment_pack"
    assert "denial_or_correction_search" in strategic.validation_requirements
    assert "second_source_confirmation" in strategic.sufficient_for_validated_digest
    assert "defillama" in strategic.preferred_providers
    protocol_business = event_source_packs.source_pack_for_playbook(
        "protocol_business_event",
        impact_path_type="protocol_business_event",
    )
    assert protocol_business.name == "protocol_business_event_pack"
    project_event = event_source_packs.source_pack_for_playbook("direct_event", impact_path_type="direct_protocol_event")
    assert project_event.name == "project_event_pack"
    security = event_source_packs.source_pack_for_playbook("security_or_regulatory_shock")
    fan = event_source_packs.source_pack_for_playbook("fan_sports_proxy")
    political = event_source_packs.source_pack_for_playbook("political_meme_proxy")
    assert "cryptopanic_tagged" in security.preferred_source_classes
    assert "cryptopanic_tagged" in fan.preferred_source_classes
    assert "cryptopanic_tagged" in political.preferred_source_classes

    pack_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "polymarket",
            "title": "SpaceX IPO odds move",
            "playbook_type": "proxy_attention",
            "impact_path_type": "venue_value_capture",
            "symbol": "VELVET",
            "coin_id": "velvet",
        },
        pack=proxy,
    )
    assert pack_eval["source_pack"] == "proxy_preipo_rwa_pack"
    assert pack_eval["source_pack_context_only"] is True
    assert pack_eval["source_pack_validated_digest_sufficient"] is False
    assert "source_is_context_only" in pack_eval["source_pack_missing_evidence"]

    listing_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "bybit_announcements",
            "title": "Bybit Will List TESTUSDT",
            "announcement_symbols": ("TEST",),
            "announcement_pairs": ("TEST/USDT",),
            "playbook_type": "listing_volatility",
            "symbol": "TEST",
            "coin_id": "test-token",
            "market_confirmation_score": 75,
        },
        pack=listing,
    )
    assert listing_eval["source_pack_validated_digest_sufficient"] is True
    assert listing_eval["source_pack_watchlist_requirements_met"] is True
    assert listing_eval["source_pack_impact_path_validating_source"] is True
    listing_mismatch = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "binance_announcements",
            "title": "Binance Will List OTHERUSDT",
            "announcement_symbols": ("OTHER",),
            "announcement_pairs": ("OTHER/USDT",),
            "playbook_type": "listing_volatility",
            "symbol": "TEST",
            "coin_id": "test-token",
            "market_confirmation_score": 75,
        },
        pack=listing,
    )
    assert listing_mismatch["source_pack_validated_digest_sufficient"] is False
    assert "symbol_or_pair_match" not in listing_mismatch["source_pack_met_requirements"]
    listing_substring_mismatch = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "binance_announcements",
            "title": "Binance Will List TESTLISTUSDT",
            "announcement_symbols": ("TESTLIST",),
            "announcement_pairs": ("TESTLIST/USDT",),
            "playbook_type": "listing_volatility",
            "symbol": "TEST",
            "coin_id": "test",
            "market_confirmation_score": 75,
        },
        pack=listing,
    )
    assert listing_substring_mismatch["source_pack_validated_digest_sufficient"] is False
    assert "symbol_or_pair_match" not in listing_substring_mismatch["source_pack_met_requirements"]

    unlock = event_source_packs.source_pack_for_playbook("unlock_supply_pressure")
    large_unlock_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "tokenomist",
            "title": "TESTUNLOCK token cliff unlock",
            "playbook_type": "unlock_supply_pressure",
            "symbol": "TESTUNLOCK",
            "coin_id": "testunlock",
            "source_url": "https://tokenomist.ai/testunlock",
            "unlock_pct_circulating": 0.12,
            "event_time": "2026-07-01T00:00:00Z",
            "as_of": "2026-06-20T00:00:00Z",
            "market_confirmation_score": 72,
        },
        pack=unlock,
    )
    assert large_unlock_eval["source_pack_validated_digest_sufficient"] is True
    assert large_unlock_eval["source_pack_watchlist_requirements_met"] is True
    assert "material_unlock" in large_unlock_eval["source_pack_met_requirements"]
    small_unlock_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "tokenomist",
            "title": "SMALL token small unlock",
            "playbook_type": "unlock_supply_pressure",
            "symbol": "SMALL",
            "coin_id": "small-token",
            "unlock_pct_circulating": 0.01,
        },
        pack=unlock,
    )
    assert small_unlock_eval["source_pack_validated_digest_sufficient"] is False
    assert "unlock_not_material" in small_unlock_eval["source_pack_missing_evidence"]
    missing_supply_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "tokenomist",
            "title": "MISS token unlock",
            "playbook_type": "unlock_supply_pressure",
            "symbol": "MISS",
            "coin_id": "missing-supply",
        },
        pack=unlock,
    )
    assert missing_supply_eval["source_pack_validated_digest_sufficient"] is False
    assert "needs_supply_materiality" in missing_supply_eval["source_pack_missing_evidence"]
    stale_unlock_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "tokenomist",
            "title": "STALE token unlock",
            "playbook_type": "unlock_supply_pressure",
            "symbol": "STALE",
            "coin_id": "stale-token",
            "unlock_pct_circulating": 0.20,
            "event_time": "2026-06-01T00:00:00Z",
            "as_of": "2026-06-20T00:00:00Z",
        },
        pack=unlock,
    )
    assert stale_unlock_eval["source_pack_validated_digest_sufficient"] is False
    assert "stale_unlock_data" in stale_unlock_eval["source_pack_missing_evidence"]

    calendar_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "coinmarketcal",
            "title": "TESTCAL mainnet launch",
            "playbook_type": "direct_event",
            "impact_path_type": "direct_protocol_event",
            "symbol": "TESTCAL",
            "coin_id": "testcal",
            "event_type": "mainnet_launch",
            "event_time": "2026-07-01T00:00:00Z",
        },
        pack=project_event,
    )
    assert calendar_eval["source_pack_validated_digest_sufficient"] is True
    assert "event_time_confirmation" in calendar_eval["source_pack_met_requirements"]
    ama_eval = event_source_packs.evaluate_pack_evidence(
        {
            "provider": "coinmarketcal",
            "title": "TESTCAL community AMA",
            "playbook_type": "direct_event",
            "impact_path_type": "direct_protocol_event",
            "symbol": "TESTCAL",
            "coin_id": "testcal",
            "event_type": "community_ama",
            "event_time": "2026-07-01T00:00:00Z",
        },
        pack=project_event,
    )
    assert ama_eval["source_pack_validated_digest_sufficient"] is False
    assert "low_authority_calendar_event" in ama_eval["source_pack_missing_evidence"]

    feed_403 = event_source_registry.feed_health_from_fetch(
        feed_url="https://example.test/rss",
        failure_type="http_403",
        rows_fetched=0,
        rows_kept=0,
        rows_rejected=0,
    )
    assert feed_403.quarantined is True
    assert feed_403.cooldown_reason == "feed_403_quarantined"
    assert feed_403.feed_source_class == feed_403.source_class
    assert feed_403.feed_quality_score <= 30

    bad_recap = event_source_registry.feed_health_from_fetch(
        feed_url="https://recap.example.test/price-prediction/rss",
        failure_count=4,
        rows_fetched=10,
        rows_kept=1,
        rows_rejected=9,
    )
    assert bad_recap.quarantined is True
    assert bad_recap.quality in {"low", "medium"}
    assert bad_recap.to_metadata()["feed_quality_score"] <= 50
    assert event_source_registry.evidence_absence_is_meaningful(
        provider="gdelt",
        source_class="broad_news",
        coverage_status="degraded",
    ) is False


def test_evidence_acquisition_final_upgrade_status_tracks_final_verdict_not_evidence_only():
    from types import SimpleNamespace
    import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition

    result = event_evidence_acquisition.EvidenceAcquisitionResult(
        acquisition_id="acq:test",
        opportunity_id="core:velvet",
        core_opportunity_id="core:velvet",
        hypothesis_id="hyp:velvet",
        incident_id="incident:spacex",
        source_pack="proxy_preipo_rwa_pack",
        status="accepted_evidence_found",
        symbol="VELVET",
        coin_id="velvet",
        accepted_evidence=({"evidence_quality_score": 92, "reason_codes": ("cryptopanic_currency_tag_match",)},),
        evidence_quality_before=70,
        evidence_quality_after=92,
        impact_path_validation_before="impact_path_validated",
        impact_path_validation_after="impact_path_validated",
        opportunity_score_before=88.5,
        opportunity_level_before="high_priority",
    )
    before = SimpleNamespace(
        opportunity_score_final=88.5,
        opportunity_level="high_priority",
        score_components={
            "opportunity_score_final": 88.5,
            "opportunity_level": "high_priority",
            "market_refresh_success": True,
            "market_confirmation_score": 100,
            "market_confirmation_level": "strong",
            "market_context_freshness_status": "fresh",
        },
    )
    after = SimpleNamespace(
        opportunity_score_final=72.5,
        opportunity_level="validated_digest",
        evidence_quality_score=92,
        impact_path_type="venue_value_capture",
        score_components={
            "opportunity_score_final": 72.5,
            "opportunity_level": "validated_digest",
            "evidence_quality_score": 92,
            "market_confirmation_score": 35,
            "market_confirmation_level": "weak",
        },
    )
    finalized = event_evidence_acquisition._finalize_result(result, before=before, after=after)

    assert finalized.acquisition_evidence_status == "accepted_evidence_found"
    assert finalized.evidence_quality_upgraded is True
    assert finalized.final_upgrade_status == "unchanged"
    assert finalized.acquisition_upgrade_status == "unchanged"
    assert finalized.opportunity_score_delta == 0
    assert finalized.post_refresh_opportunity_level == "validated_digest"
    assert finalized.post_refresh_market_confirmation_score == 100
    assert finalized.post_refresh_market_confirmation_level == "strong"
    assert finalized.market_data_freshness == "fresh"
    assert finalized.market_reaction_confirmation == "strong"
    assert finalized.final_opportunity_level == "high_priority"
    assert finalized.final_verdict_source == "market_refresh"

    quality = event_alpha_quality_fields.ensure_quality_fields({
        "opportunity_score_final": 72.5,
        "opportunity_level": "validated_digest",
        "final_opportunity_score": 88.5,
        "final_opportunity_level": "high_priority",
    })
    assert quality["opportunity_score_final"] == 88.5
    assert quality["opportunity_level"] == "high_priority"


def test_evidence_acquisition_core_opportunity_dedupes_supporting_rows():
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition

    base = {
        "event_cluster_id": "cluster:spacex",
        "incident_id": "incident:spacex",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "validated_symbol": "VELVET",
        "validated_coin_id": "velvet",
        "external_asset": "SpaceX",
        "playbook_type": "proxy_attention",
        "impact_category": "tokenized_stock_venue",
        "impact_path_type": "venue_value_capture",
        "candidate_role": "proxy_venue",
        "source_class": "crypto_news",
        "evidence_specificity": "asset_and_catalyst",
        "evidence_quality_score": 80,
        "market_confirmation_score": 60,
        "opportunity_score_final": 74,
        "opportunity_level": "validated_digest",
    }
    rows = (
        {**base, "hypothesis_id": "hyp:velvet:primary"},
        {**base, "hypothesis_id": "hyp:velvet:supporting", "impact_category": "rwa_preipo_proxy"},
    )
    result = event_evidence_acquisition.run_evidence_acquisition(
        rows,
        provider=None,
        providers_by_hint={},
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(enabled=True, max_candidates=5, max_queries=1),
    )
    assert result.attempted == 1
    assert result.results[0].core_opportunity_id
    assert result.results[0].core_opportunity_id != "UNKNOWN"


def test_evidence_acquisition_empty_and_provider_failures_return_complete_result():
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition

    disabled = event_evidence_acquisition.run_evidence_acquisition(
        (),
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(enabled=False),
    )
    assert disabled.status == "disabled"
    assert disabled.results == ()
    assert disabled.attempted == 0

    no_candidates = event_evidence_acquisition.run_evidence_acquisition(
        (),
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(enabled=True),
    )
    assert no_candidates.status == "no_candidates"
    assert no_candidates.results == ()
    assert no_candidates.attempted == 0

    class FailingProvider:
        name = "fixture_dns_failure"

        def search(self, queries, *, max_results_per_query, now=None):
            raise OSError("DNS temporary failure in name resolution")

    row = {
        "hypothesis_id": "hyp:tao-provider-fail",
        "core_opportunity_id": "agg:tao-provider-fail",
        "symbol": "TAO",
        "coin_id": "bittensor",
        "validated_symbol": "TAO",
        "validated_coin_id": "bittensor",
        "external_asset": "Bittensor",
        "playbook_type": "strategic_investment",
        "impact_category": "strategic_investment_or_valuation",
        "impact_path_type": "strategic_investment_or_valuation",
        "candidate_role": "direct_subject",
        "opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "source_pack": "strategic_investment_pack",
    }
    failed = event_evidence_acquisition.run_evidence_acquisition(
        (row,),
        provider=FailingProvider(),
        providers_by_hint={},
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(
            enabled=True,
            max_candidates=1,
            max_queries=1,
        ),
    )
    assert failed.status == "failed_soft"
    assert failed.attempted == 1
    assert failed.results[0].status == "failed_soft"
    assert failed.results[0].query_results[0].status == "failed_soft"
    assert any("OSError" in warning for warning in failed.results[0].warnings)


def test_event_evidence_acquisition_executes_fixture_searches():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    rune = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:rune-acquisition",
        event_cluster_id="cluster:rune",
        event_type="security_incident",
        external_asset="THORChain",
        impact_category="security_or_regulatory_shock",
        candidate_sectors=("defi_tokens",),
        candidate_symbols=("RUNE",),
        candidate_coin_ids=("thorchain",),
        impact_path_type="exploit_security_event",
        playbook_hint="security_or_regulatory_shock",
        confidence=0.78,
        hypothesis_score=64.0,
        opportunity_score_final=64.0,
        opportunity_level="exploratory",
        missing_requirements=("source evidence", "impact_path_validation"),
        validation_stage="catalyst_link_validated",
        score_components={
            "symbol": "RUNE",
            "coin_id": "thorchain",
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "playbook_type": "security_or_regulatory_shock",
            "impact_path_type": "exploit_security_event",
            "opportunity_score_final": 64.0,
            "opportunity_level": "exploratory",
            "missing_requirements": ("source evidence", "impact_path_validation"),
        },
    )
    fetched = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    accepted_raw = RawDiscoveredEvent(
        raw_id="raw:rune-accepted",
        provider="cryptopanic",
        fetched_at=fetched,
        published_at=fetched,
        source_url="https://cryptopanic.com/news/rune-exploit",
        title="RUNE exploit update: THORChain resumes trading after incident",
        body="RUNE and THORChain markets reacted after an exploit; the project resumes trading and publishes the security update.",
        raw_json={"currency_tags": ("RUNE",), "currencies": [{"code": "RUNE", "slug": "thorchain"}], "source_origin": "CryptoPanic"},
        source_confidence=0.88,
        content_hash="rune-accepted",
    )
    rejected_raw = RawDiscoveredEvent(
        raw_id="raw:rune-rejected",
        provider="polymarket",
        fetched_at=fetched,
        published_at=fetched,
        source_url="https://polymarket.com/event/thorchain-hack",
        title="Will THORChain exploit be resolved this week?",
        body="Prediction market context tracks the exploit resolution, but does not mention RUNE token identity or market impact.",
        raw_json={"source_origin": "Polymarket"},
        source_confidence=0.70,
        content_hash="rune-rejected",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider(rows_by_query={
        "RUNE hack incident security market reaction": (accepted_raw,),
        "RUNE exploit official update": (rejected_raw,),
    })
    with TemporaryDirectory() as tmp:
        artifact_path = Path(tmp) / "event_evidence_acquisition.jsonl"
        result = event_evidence_acquisition.run_evidence_acquisition(
            (rune,),
            provider=provider,
            providers_by_hint={"cryptopanic": provider, "project_blog_rss": provider},
            cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(
                enabled=True,
                max_candidates=3,
                max_queries=4,
                max_results_per_query=2,
                fixture_only=True,
                artifact_path=artifact_path,
            ),
            now=fetched,
            run_context={"run_id": "run:test", "profile": "quality_validation", "run_mode": "test", "artifact_namespace": "quality_validation"},
        )
        assert result.attempted == 1
        assert result.accepted == 1
        assert result.rows_written == 1
        assert result.results[0].status == "accepted_evidence_found"
        assert any("cryptopanic_currency_tag_match" in item["reason_codes"] for item in result.results[0].accepted_evidence)
        accepted_sample = result.results[0].accepted_evidence[0]
        assert accepted_sample["source_class"] == "cryptopanic_tagged"
        assert "RUNE" in accepted_sample["currency_tags"]
        assert "THORCHAIN" in accepted_sample["currency_tags"]
        assert accepted_sample["cryptopanic_currency_tag_match"] is True
        assert accepted_sample["source_pack_impact_path_validating_source"] is True
        assert accepted_sample["source_pack_validated_digest_sufficient"] is True
        assert "impact_path_validation" in accepted_sample["source_can_prove"]
        assert result.path == artifact_path
        rows = event_evidence_acquisition.load_acquisition_results(artifact_path)
        assert rows[0]["symbol"] == "RUNE"
        assert rows[0]["coin_id"] == "thorchain"
        assert rows[0]["accepted_evidence"]
        assert rows[0]["evidence_acquisition_attempted"] is True
        assert rows[0]["evidence_acquisition_plan"]["source_pack"] == "security_shock_pack"
        assert rows[0]["evidence_acquisition_results"]["status"] == "accepted_evidence_found"
        assert "accepted_evidence_found" in rows[0]["query_execution_statuses"]
        assert "impact_path_validation" in rows[0]["source_can_prove"]
        assert "token_identity_validation" in rows[0]["source_can_prove"]
        assert "security_or_regulatory_shock" in rows[0]["source_useful_playbooks"]
        assert "official_confirmation" in rows[0]["source_cannot_prove"]


def test_event_evidence_acquisition_accepts_structured_tokenomist_unlocks():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    from crypto_rsi_scanner.event_providers.tokenomist import TokenomistProvider

    _coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    now = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    unlock = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:testunlock-acquisition",
        event_cluster_id="cluster:testunlock",
        event_type="token_unlock",
        external_asset="Test Unlock",
        impact_category="unlock_supply_pressure",
        candidate_sectors=("direct_token_events",),
        candidate_symbols=("TESTUNLOCK",),
        candidate_coin_ids=("testunlock",),
        impact_path_type="unlock_supply_event",
        playbook_hint="unlock_supply_pressure",
        confidence=0.82,
        hypothesis_score=68.0,
        opportunity_score_final=68.0,
        opportunity_level="validated_digest",
        missing_requirements=("market_confirmation",),
        validation_stage="impact_path_validated",
        score_components={
            "symbol": "TESTUNLOCK",
            "coin_id": "testunlock",
            "validated_symbol": "TESTUNLOCK",
            "validated_coin_id": "testunlock",
            "playbook_type": "unlock_supply_pressure",
            "impact_path_type": "unlock_supply_event",
            "opportunity_score_final": 68.0,
            "opportunity_level": "validated_digest",
            "market_confirmation_score": 72,
        },
    )
    provider = event_catalyst_search.EventProviderCatalystSearchProvider(
        lambda query: TokenomistProvider(tokenomist_path),
        name="tokenomist",
        filter_by_query=True,
        max_fetches_per_search=1,
    )
    with TemporaryDirectory() as tmp:
        artifact_path = Path(tmp) / "event_evidence_acquisition.jsonl"
        result = event_evidence_acquisition.run_evidence_acquisition(
            (unlock,),
            provider=provider,
            providers_by_hint={"tokenomist": provider},
            cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(
                enabled=True,
                max_candidates=1,
                max_queries=2,
                max_results_per_query=2,
                fixture_only=False,
                artifact_path=artifact_path,
            ),
            now=now,
            run_context={
                "run_id": "run:testunlock",
                "profile": "structured_source_pack",
                "run_mode": "test",
                "artifact_namespace": "structured_source_pack",
            },
        )
    assert result.attempted == 1
    assert result.accepted == 1
    accepted = result.results[0].accepted_evidence[0]
    assert accepted["source_class"] == "structured_unlock"
    assert accepted["unlock_pct_circulating"] == 0.12
    assert accepted["unlock_materiality"] == "large"
    assert "structured_unlock_source" in accepted["reason_codes"]
    assert "material_unlock" in accepted["reason_codes"]
    assert accepted["source_pack_validated_digest_sufficient"] is True
    assert accepted["source_pack_watchlist_requirements_met"] is True
    card_sample = event_research_cards._accepted_evidence_sample_text(accepted)
    audit_sample = event_opportunity_audit._accepted_evidence_sample_text(accepted)
    assert "unlock_pct=0.12" in card_sample
    assert "materiality=large" in audit_sample


def test_event_evidence_acquisition_accepts_official_exchange_announcements_only_on_identity_match():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_providers.binance_announcements import BinanceAnnouncementProvider
    from crypto_rsi_scanner.event_providers.bybit_announcements import BybitAnnouncementProvider

    now = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    listing_raw = BinanceAnnouncementProvider(binance_path, required=True).fetch_events(start, end)[0]
    perp_raw = BybitAnnouncementProvider(bybit_path, required=True).fetch_events(start, end)[0]

    listing = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:testlist-listing",
        event_cluster_id="cluster:testlist",
        event_type="exchange_listing",
        external_asset="Binance",
        impact_category="listing_liquidity_event",
        candidate_sectors=("direct_token_events",),
        candidate_symbols=("TESTLIST",),
        candidate_coin_ids=("testlist",),
        impact_path_type="listing_liquidity_event",
        playbook_hint="listing_volatility",
        confidence=0.82,
        hypothesis_score=66.0,
        opportunity_score_final=66.0,
        opportunity_level="validated_digest",
        validation_stage="impact_path_validated",
        score_components={
            "symbol": "TESTLIST",
            "coin_id": "testlist",
            "validated_symbol": "TESTLIST",
            "validated_coin_id": "testlist",
            "playbook_type": "listing_volatility",
            "impact_path_type": "listing_liquidity_event",
            "opportunity_score_final": 66.0,
            "opportunity_level": "validated_digest",
        },
    )
    perp = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:testperp-listing",
        event_cluster_id="cluster:testperp",
        event_type="perp_listing",
        external_asset="Bybit",
        impact_category="perp_listing",
        candidate_sectors=("direct_token_events",),
        candidate_symbols=("TESTPERP",),
        candidate_coin_ids=("testperp",),
        impact_path_type="perp_listing",
        playbook_hint="perp_listing_squeeze",
        confidence=0.82,
        hypothesis_score=67.0,
        opportunity_score_final=67.0,
        opportunity_level="validated_digest",
        validation_stage="impact_path_validated",
        score_components={
            "symbol": "TESTPERP",
            "coin_id": "testperp",
            "validated_symbol": "TESTPERP",
            "validated_coin_id": "testperp",
            "playbook_type": "perp_listing_squeeze",
            "impact_path_type": "perp_listing",
            "opportunity_score_final": 67.0,
            "opportunity_level": "validated_digest",
        },
    )
    mismatch = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:other-listing",
        event_cluster_id="cluster:other",
        event_type="exchange_listing",
        external_asset="Binance",
        impact_category="listing_liquidity_event",
        candidate_sectors=("direct_token_events",),
        candidate_symbols=("OTHER",),
        candidate_coin_ids=("other"),
        impact_path_type="listing_liquidity_event",
        playbook_hint="listing_volatility",
        confidence=0.82,
        hypothesis_score=66.0,
        opportunity_score_final=66.0,
        opportunity_level="validated_digest",
        validation_stage="impact_path_validated",
        score_components={
            "symbol": "OTHER",
            "coin_id": "other",
            "validated_symbol": "OTHER",
            "validated_coin_id": "other",
            "playbook_type": "listing_volatility",
            "impact_path_type": "listing_liquidity_event",
            "opportunity_score_final": 66.0,
            "opportunity_level": "validated_digest",
        },
    )
    substring_mismatch = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:test-substring-listing",
        event_cluster_id="cluster:test-substring",
        event_type="exchange_listing",
        external_asset="Binance",
        impact_category="listing_liquidity_event",
        candidate_sectors=("direct_token_events",),
        candidate_symbols=("TEST",),
        candidate_coin_ids=("test"),
        impact_path_type="listing_liquidity_event",
        playbook_hint="listing_volatility",
        confidence=0.82,
        hypothesis_score=66.0,
        opportunity_score_final=66.0,
        opportunity_level="validated_digest",
        validation_stage="impact_path_validated",
        score_components={
            "symbol": "TEST",
            "coin_id": "test",
            "validated_symbol": "TEST",
            "validated_coin_id": "test",
            "playbook_type": "listing_volatility",
            "impact_path_type": "listing_liquidity_event",
            "opportunity_score_final": 66.0,
            "opportunity_level": "validated_digest",
        },
    )

    provider = event_catalyst_search.FixtureCatalystSearchProvider(rows_by_query={
        "TESTLIST listing announcement": (listing_raw,),
        "TESTPERP perpetual futures listing announcement": (perp_raw,),
        "OTHER listing announcement": (listing_raw,),
        "TEST listing announcement": (listing_raw,),
    })
    result = event_evidence_acquisition.run_evidence_acquisition(
        (listing, perp, mismatch, substring_mismatch),
        provider=provider,
        providers_by_hint={"official_exchange": provider},
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(
            enabled=True,
            max_candidates=4,
            max_queries=8,
            max_results_per_query=2,
            fixture_only=True,
        ),
        now=now,
    )

    by_hypothesis = {item.hypothesis_id: item for item in result.results}
    listing_result = by_hypothesis["hyp:testlist-listing"]
    perp_result = by_hypothesis["hyp:testperp-listing"]
    mismatch_result = by_hypothesis["hyp:other-listing"]
    substring_mismatch_result = by_hypothesis["hyp:test-substring-listing"]
    assert listing_result.status == "accepted_evidence_found"
    assert perp_result.status == "accepted_evidence_found"
    listing_evidence = listing_result.accepted_evidence[0]
    perp_evidence = perp_result.accepted_evidence[0]
    assert listing_evidence["source_class"] == "official_exchange"
    assert listing_evidence["exchange"] == "binance"
    assert listing_evidence["announcement_kind"] == "exchange_listing"
    assert listing_evidence["announcement_pairs"] == ("TESTLIST/USDT",)
    assert "official_exchange_listing" in listing_evidence["reason_codes"]
    assert listing_evidence["source_pack_validated_digest_sufficient"] is True
    assert listing_evidence["source_pack_watchlist_requirements_met"] is False
    assert perp_evidence["exchange"] == "bybit"
    assert perp_evidence["announcement_kind"] == "perp_listing"
    assert perp_evidence["announcement_contracts"] == ("TESTPERPUSDT",)
    assert perp_evidence["source_pack_validated_digest_sufficient"] is True
    assert perp_evidence["source_pack_watchlist_requirements_met"] is False
    assert mismatch_result.status == "rejected_results_only"
    assert "token_identity_rejected" in mismatch_result.rejected_evidence[0]["reason_codes"]
    assert substring_mismatch_result.status == "rejected_results_only"
    assert "token_identity_rejected" in substring_mismatch_result.rejected_evidence[0]["reason_codes"]


def test_event_evidence_acquisition_rejects_cryptopanic_tag_mismatch_and_heat_only():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    rune = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:rune-hot-rejected",
        event_cluster_id="cluster:rune-hot",
        event_type="security_incident",
        external_asset="THORChain",
        impact_category="security_or_regulatory_shock",
        candidate_sectors=("defi_tokens",),
        candidate_symbols=("RUNE",),
        candidate_coin_ids=("thorchain",),
        impact_path_type="exploit_security_event",
        playbook_hint="security_or_regulatory_shock",
        confidence=0.78,
        hypothesis_score=64.0,
        opportunity_score_final=64.0,
        opportunity_level="exploratory",
        missing_requirements=("source evidence", "impact_path_validation"),
        validation_stage="catalyst_link_validated",
        score_components={
            "symbol": "RUNE",
            "coin_id": "thorchain",
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "playbook_type": "security_or_regulatory_shock",
            "impact_path_type": "exploit_security_event",
            "opportunity_score_final": 64.0,
            "opportunity_level": "exploratory",
        },
    )
    fetched = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    hot_but_unrelated = RawDiscoveredEvent(
        raw_id="raw:rune-hot-unrelated",
        provider="cryptopanic",
        fetched_at=fetched,
        published_at=fetched,
        source_url="https://cryptopanic.com/news/btc-hot",
        title="Bullish crypto market heat lifts majors",
        body="CryptoPanic marks this as hot and bullish. RUNE is only mentioned in a broad market recap without incident details.",
        raw_json={"currency_tags": ("BTC",), "kind": "hot", "source_origin": "CryptoPanic"},
        source_confidence=0.88,
        content_hash="rune-hot-unrelated",
    )
    provider = event_catalyst_search.FixtureCatalystSearchProvider(rows_by_query={
        "RUNE hack incident security market reaction": (hot_but_unrelated,),
        "RUNE exploit official update": (),
    })
    result = event_evidence_acquisition.run_evidence_acquisition(
        (rune,),
        provider=provider,
        providers_by_hint={"cryptopanic": provider, "project_blog_rss": provider},
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(
            enabled=True,
            max_candidates=1,
            max_queries=2,
            max_results_per_query=2,
            fixture_only=True,
        ),
        now=fetched,
    )

    assert result.accepted == 0
    assert result.results[0].status == "rejected_results_only"
    rejected_reasons = set(result.results[0].rejected_evidence[0]["reason_codes"])
    assert "cryptopanic_currency_tag_mismatch" in rejected_reasons
    assert "cryptopanic_narrative_heat_only" in rejected_reasons


def test_event_evidence_acquisition_provider_unavailable_and_operator_surfaces():
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    velvet = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:velvet-acquisition",
        event_cluster_id="cluster:spacex",
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category="tokenized_stock_venue",
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET",),
        candidate_coin_ids=("velvet",),
        impact_path_type="venue_value_capture",
        candidate_role="proxy_venue",
        playbook_hint="proxy_attention",
        confidence=0.82,
        hypothesis_score=72.0,
        opportunity_score_final=72.0,
        opportunity_level="validated_digest",
        validation_stage="impact_path_validated",
        score_components={
            "symbol": "VELVET",
            "coin_id": "velvet",
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "external_asset": "SpaceX",
            "playbook_type": "proxy_attention",
            "impact_category": "tokenized_stock_venue",
            "impact_path_type": "venue_value_capture",
            "candidate_role": "proxy_venue",
            "opportunity_score_final": 72.0,
            "opportunity_level": "validated_digest",
        },
    )
    unavailable = event_evidence_acquisition.run_evidence_acquisition(
        (velvet,),
        provider=None,
        providers_by_hint={},
        cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(enabled=True, max_candidates=1, max_queries=1),
    )
    assert unavailable.results[0].status == "provider_unavailable"
    assert unavailable.results[0].query_results[0].evidence_absence_is_meaningful is True

    provider = event_catalyst_search.FixtureCatalystSearchProvider(rows_by_query={
        "VELVET SpaceX pre IPO tokenized stock": (
            event_catalyst_search._raw_event_from_fixture({
                "raw_id": "raw:velvet-acquisition",
                "provider": "cryptopanic",
                "source_url": "https://cryptopanic.com/news/velvet-spacex",
                "title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
                "body": "Velvet users can trade SpaceX pre-IPO exposure through tokenized stock markets, explaining VELVET venue value capture.",
                "raw_json": {"currency_tags": ["VELVET"], "source_origin": "CryptoPanic"},
                "source_confidence": 0.90,
            }),
        ),
        "SpaceX prediction market VELVET": (
            event_catalyst_search._raw_event_from_fixture({
                "raw_id": "raw:spacex-context-only",
                "provider": "polymarket",
                "source_url": "https://polymarket.com/event/spacex-ipo",
                "title": "SpaceX IPO prediction market volume rises",
                "body": "Prediction market context for SpaceX IPO odds; no VELVET token or venue value capture is described.",
                "raw_json": {"source_origin": "Polymarket"},
                "source_confidence": 0.70,
            }),
        ),
    })
    with TemporaryDirectory() as tmp:
        artifact_path = Path(tmp) / "event_evidence_acquisition.jsonl"
        result = event_evidence_acquisition.run_evidence_acquisition(
            (velvet,),
            provider=provider,
            providers_by_hint={"cryptopanic": provider, "polymarket": provider, "project_blog_rss": provider},
            cfg=event_evidence_acquisition.EvidenceAcquisitionConfig(
                enabled=True,
                max_candidates=1,
                max_queries=3,
                fixture_only=True,
                artifact_path=artifact_path,
            ),
            run_context={"profile": "quality_validation", "artifact_namespace": "quality_validation", "run_mode": "test"},
        )
        rows = event_evidence_acquisition.load_acquisition_results(artifact_path)
    brief = event_alpha_daily_brief.build_daily_brief(
        evidence_acquisition_rows=rows,
        requested_profile="quality_validation",
        artifact_namespace="quality_validation",
        include_test_artifacts=True,
    )
    assert "Executed source-pack searches" in brief
    assert "VELVET" in brief
    assert "accepted=1" in brief
    assert rows[0]["evidence_acquisition_plan"]["query_count"] == 3
    assert rows[0]["evidence_acquisition_results"]["accepted"] == 1
    assert rows[0]["provider_coverage_statuses"] == ["complete"]

    updated = result.hypotheses[0]
    components = dict(updated.score_components)
    assert components["evidence_acquisition_status"] == "accepted_evidence_found"
    assert components["evidence_acquisition_accepted_count"] == 1
    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="hypothesis|cluster:spacex|velvet",
        cluster_id="cluster:spacex",
        event_id="hyp:velvet-acquisition",
        coin_id="velvet",
        symbol="VELVET",
        relationship_type="impact_hypothesis",
        external_asset="SpaceX",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=None,
        first_seen_at="2026-06-15T12:00:00+00:00",
        last_seen_at="2026-06-15T12:00:00+00:00",
        latest_source="cryptopanic",
        latest_playbook_type="proxy_attention",
        latest_score_components=components,
    )
    card = event_research_cards.render_research_card(entry.key, watchlist_entries=[entry])
    assert "Evidence acquisition result: status=accepted_evidence_found" in card.markdown
    assert "Accepted evidence reasons:" in card.markdown
    audit = event_opportunity_audit.format_opportunity_audit("VELVET", hypotheses=[updated], watchlist_entries=[entry])
    assert "execution result: status=accepted_evidence_found" in audit
    assert "accepted reason codes:" in audit


def test_event_alpha_evidence_acquisition_smoke_target_exists():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-evidence-acquisition-smoke" in makefile
    profiles = Path("crypto_rsi_scanner/event_alpha/config/profiles.py").read_text(encoding="utf-8")
    assert "evidence_acquisition_smoke" in profiles
    assert "EVENT_ALPHA_EVIDENCE_ACQUISITION_FIXTURE_ONLY" in profiles


def test_core_evidence_acquisition_view_aggregates_canonical_rows():
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    rows = _canonical_core_fixture_rows()
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-acquisition-view",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(path, latest_run=True).rows
    by_symbol = {row["symbol"]: row for row in core_rows}
    acquisition_rows = [
        {
            "row_type": "event_evidence_acquisition",
            "core_opportunity_id": by_symbol["VELVET"]["core_opportunity_id"],
            "symbol": "VELVET",
            "coin_id": "velvet",
            "source_pack": "proxy_preipo_rwa_pack",
            "status": "accepted_evidence_found",
            "accepted_evidence": [{
                "title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
                "reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
            }],
            "evidence_quality_before": 60,
            "evidence_quality_after": 91,
            "opportunity_score_before": 70,
            "opportunity_score_after": 92,
            "opportunity_level_before": "validated_digest",
            "opportunity_level_after": "high_priority",
        },
        {
            "row_type": "event_evidence_acquisition",
            "core_opportunity_id": by_symbol["RUNE"]["core_opportunity_id"],
            "symbol": "RUNE",
            "coin_id": "thorchain",
            "source_pack": "security_shock_pack",
            "status": "accepted_evidence_found",
            "accepted_evidence": [{
                "title": "RUNE exploit update: THORChain resumes trading after incident",
                "reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
            }],
        },
        {
            "row_type": "event_evidence_acquisition",
            "core_opportunity_id": by_symbol["AAVE"]["core_opportunity_id"],
            "symbol": "AAVE",
            "coin_id": "aave",
            "source_pack": "strategic_investment_pack",
            "status": "no_results",
        },
        {
            "row_type": "event_evidence_acquisition",
            "core_opportunity_id": by_symbol["MEME"]["core_opportunity_id"],
            "symbol": "MEME",
            "coin_id": "memecore",
            "source_pack": "market_anomaly_pack",
            "status": "no_results",
        },
    ]

    velvet = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
        by_symbol["VELVET"]["core_opportunity_id"],
        core_rows=[by_symbol["VELVET"]],
        evidence_acquisition_rows=acquisition_rows,
    )
    rune = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
        by_symbol["RUNE"]["core_opportunity_id"],
        core_rows=[by_symbol["RUNE"]],
        evidence_acquisition_rows=acquisition_rows,
    )
    aave = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
        by_symbol["AAVE"]["core_opportunity_id"],
        core_rows=[by_symbol["AAVE"]],
        evidence_acquisition_rows=acquisition_rows,
    )
    meme = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
        by_symbol["MEME"]["core_opportunity_id"],
        core_rows=[by_symbol["MEME"]],
        evidence_acquisition_rows=acquisition_rows,
    )
    assert velvet.accepted_evidence_count == 1
    assert velvet.source_pack == "proxy_preipo_rwa_pack"
    assert "cryptopanic_currency_tag_match" in velvet.accepted_reason_codes
    assert "direct_token_mechanism" in velvet.accepted_reason_codes
    assert velvet.accepted_evidence_samples[0]["title"].startswith("VELVET offers SpaceX")
    assert rune.accepted_evidence_count == 1
    assert "RUNE exploit update" in rune.accepted_evidence_samples[0]["title"]
    assert aave.acquisition_status == "no_results"
    assert aave.source_pack == "strategic_investment_pack"
    assert meme.acquisition_status == "no_results"
    assert meme.source_pack == "market_anomaly_pack"


def test_evidence_acquisition_rows_reconcile_to_canonical_core_store_ids():
    import json
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-core-acquisition",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        meme_core = next(row["core_opportunity_id"] for row in core_rows if row["coin_id"] == "memecore")
        acquisition_path = root / "event_evidence_acquisition.jsonl"
        acquisition_path.write_text(
            json.dumps({
                "row_type": "event_evidence_acquisition",
                "run_id": "run-core-acquisition",
                "profile": "market_refresh_smoke",
                "artifact_namespace": "market_refresh_smoke",
                "core_opportunity_id": "core_api_memecore",
                "hypothesis_id": "hyp-meme-core",
                "incident_id": "incident-memecore",
                "symbol": "MEME",
                "coin_id": "memecore",
            }) + "\n",
            encoding="utf-8",
        )
        changed = event_evidence_acquisition.reconcile_acquisition_core_ids(
            acquisition_path,
            core_rows,
            run_id="run-core-acquisition",
            profile="market_refresh_smoke",
            artifact_namespace="market_refresh_smoke",
        )
        rows = event_evidence_acquisition.load_acquisition_results(acquisition_path)
    assert changed >= 1
    assert rows[0]["core_opportunity_id"] == meme_core
    assert rows[0]["core_opportunity_id_status"] == "diagnostic_support"
    assert rows[0]["original_core_opportunity_id"] == "core_api_memecore"


def test_evidence_acquisition_caps_stale_promoted_final_fields():
    import json
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition as event_evidence_acquisition

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        acquisition_path = root / "event_evidence_acquisition.jsonl"
        acquisition_path.write_text(
            json.dumps({
                "row_type": "event_evidence_acquisition",
                "run_id": "run-acq-cap",
                "profile": "live_burn_in_no_send",
                "artifact_namespace": "live_burn_in_no_send",
                "core_opportunity_id": "core_tao",
                "symbol": "TAO",
                "coin_id": "bittensor",
                "status": "rejected_results_only",
                "accepted_evidence_count": 0,
                "final_opportunity_level": "validated_digest",
                "final_route_after_quality_gate": "RESEARCH_DIGEST",
                "final_state_after_quality_gate": "WATCHLIST",
            }) + "\n",
            encoding="utf-8",
        )
        changed = event_evidence_acquisition.reconcile_acquisition_core_ids(
            acquisition_path,
            [{
                "row_type": "event_core_opportunity",
                "core_opportunity_id": "core_tao",
                "symbol": "TAO",
                "coin_id": "bittensor",
                "final_opportunity_level": "validated_digest",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "final_route_after_quality_gate": "RESEARCH_DIGEST",
                "final_state_after_quality_gate": "WATCHLIST",
            }],
            run_id="run-acq-cap",
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
        )
        rows = event_evidence_acquisition.load_acquisition_results(acquisition_path)

    assert changed >= 1
    assert rows[0]["core_opportunity_id"] == "core_tao"
    assert rows[0]["opportunity_type"] == "UNCONFIRMED_RESEARCH"
    assert rows[0]["final_opportunity_level"] == "exploratory"
    assert rows[0]["final_route_after_quality_gate"] == "STORE_ONLY"
    assert rows[0]["final_state_after_quality_gate"] == "RADAR"
    assert rows[0]["acquisition_final_level_normalized"] is True
    assert rows[0]["final_verdict_reason"] == "rejected_results_only_not_confirmation"


def test_source_coverage_reconciles_cryptopanic_backoff_after_successful_request():
    import json

    import crypto_rsi_scanner.event_alpha.radar.source_coverage as event_alpha_source_coverage
    import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        ledger = base / "cryptopanic_request_ledger.jsonl"
        ledger.write_text(
            json.dumps({
                "timestamp": "2026-07-01T00:00:00+00:00",
                "status_code": 200,
                "currencies": "CHZ",
                "normalized_request_key": "growth_weekly|CHZ",
            }) + "\n",
            encoding="utf-8",
        )
        report = event_alpha_source_coverage.build_source_coverage_report(
            provider_status_report=event_provider_status.EventDiscoveryProviderStatus(
                mode="research_only",
                cache_dir=str(base),
                lookback_hours=72,
                horizon_days=14,
                sources=(event_provider_status.ProviderStatus("cryptopanic", "event", True),),
                enrichment=(),
                warnings=(),
                next_steps=(),
            ),
            provider_health_rows={
                "cryptopanic:event_source": {
                    "provider_key": "cryptopanic:event_source",
                    "provider": "cryptopanic",
                    "provider_service": "event_source",
                    "disabled_until": "2026-07-01T01:00:00+00:00",
                }
            },
            evidence_acquisition_rows=[{
                "source_pack": "fan_sports_pack",
                "accepted_evidence": [{"provider": "cryptopanic", "source_class": "cryptopanic_tagged"}],
            }],
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep_cryptopanic_rehearsal",
            cryptopanic_request_ledger_path=ledger,
            now=pd.Timestamp("2026-07-01T00:30:00Z").to_pydatetime(),
        )
    assert report.cryptopanic_health_status == "healthy"
    assert report.cryptopanic_backoff_reconciled_after_success is True
    assert report.cryptopanic_successful_requests == 1


def test_cryptopanic_run_stats_dedupes_query_and_result_accepted_evidence():
    import json

    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health

    old_health_path = config.EVENT_PROVIDER_HEALTH_PATH
    old_token = config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN
    old_live = config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE
    old_path = config.EVENT_DISCOVERY_CRYPTOPANIC_PATH
    try:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            health_path = base / "event_provider_health.json"
            config.EVENT_PROVIDER_HEALTH_PATH = health_path
            config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN = "test-token"
            config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE = True
            config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = None
            event_provider_health.write_provider_health(health_path, {})
            ledger = health_path.with_name("cryptopanic_request_ledger.jsonl")
            ledger.write_text(
                json.dumps({
                    "timestamp": "2026-07-01T00:00:00+00:00",
                    "status_code": 200,
                    "currencies": "CHZ",
                    "normalized_request_key": "growth_weekly|CHZ",
                }) + "\n",
                encoding="utf-8",
            )
            evidence = {"provider": "cryptopanic", "source_url": "https://example.test/chz", "title": "CHZ World Cup demand"}
            result = SimpleNamespace(
                evidence_acquisition_result=SimpleNamespace(results=[
                    SimpleNamespace(
                        providers_used=("cryptopanic",),
                        query_results=(SimpleNamespace(
                            provider_hint="cryptopanic",
                            provider_used="cryptopanic",
                            query="CHZ",
                            results_seen=1,
                            provider_failures=(),
                            accepted_evidence=(evidence,),
                            rejected_evidence=(),
                        ),),
                        accepted_evidence=(evidence,),
                        rejected_evidence=(),
                        provider_failures=(),
                    )
                ])
            )
            stats = scanner._cryptopanic_stats_for_pipeline_result(result, provider_health_path=health_path)
    finally:
        config.EVENT_PROVIDER_HEALTH_PATH = old_health_path
        config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN = old_token
        config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE = old_live
        config.EVENT_DISCOVERY_CRYPTOPANIC_PATH = old_path
    assert stats["cryptopanic_accepted_evidence"] == 1
    assert stats["cryptopanic_successful_requests"] == 1


def test_research_card_source_coverage_uses_authoritative_json():
    import json
    from datetime import datetime, timezone

    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        cards_dir = base / "research_cards"
        (base / "event_alpha_source_coverage.json").write_text(
            json.dumps({
                "packs": [{
                    "source_pack": "fan_sports_pack",
                    "provider_coverage_status": "partial",
                    "evidence_absence_meaningful": True,
                    "providers_missing_for_confirmation": ["sports_fixtures"],
                    "providers_degraded_for_confirmation": ["gdelt", "project_blog_rss"],
                    "missing_providers": ["sports_fixtures"],
                    "degraded_or_backoff_providers": ["gdelt", "project_blog_rss"],
                    "coverage_gap_reason": "source_pack_coverage_partial;missing:sports_fixtures;degraded:gdelt,project_blog_rss",
                }]
            }),
            encoding="utf-8",
        )
        core_row = {
            "row_type": "event_core_opportunity",
            "schema_version": "event_core_opportunity_store_v1",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "artifact_namespace": "ns",
            "core_opportunity_id": "core_chz_review",
            "symbol": "CHZ",
            "coin_id": "chiliz",
            "incident_id": "world-cup-chz",
            "canonical_incident_name": "World Cup fan token attention",
            "candidate_role": "proxy_instrument",
            "primary_impact_path": "fan_token_event",
            "impact_path_type": "fan_token_event",
            "opportunity_level": "exploratory",
            "final_opportunity_level": "exploratory",
            "opportunity_score_final": 64,
            "final_route_after_quality_gate": "STORE_ONLY",
            "final_state_after_quality_gate": "RADAR",
            "source_pack": "fan_sports_pack",
            "provider_coverage_status": "complete",
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_acquisition_accepted_count": 1,
            "evidence_acquisition_accepted_evidence": [{
                "provider": "cryptopanic",
                "source_class": "cryptopanic_tagged",
                "title": "CHZ fan token demand builds into World Cup",
            }],
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
            "generated_at": "2026-07-01T00:00:00+00:00",
        }
        result = event_research_cards.write_research_cards(
            cards_dir,
            watchlist_entries=[],
            alert_rows=[core_row],
            now=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert result.cards_written == 1
        text = result.card_paths[0].read_text(encoding="utf-8")
    assert "- Coverage status: partial" in text
    assert "missing:sports_fixtures" in text
    assert "degraded:gdelt" in text
    assert "Provider/source gaps: none" not in text


def test_market_reaction_rejected_evidence_is_unconfirmed_research():
    import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction

    result = event_market_reaction.evaluate_market_reaction({
        "source_class": "broad_news",
        "source_pack": "strategic_investment_pack",
        "impact_path_type": "strategic_investment",
        "evidence_quality_score": 42,
        "evidence_acquisition_status": "rejected_results_only",
        "market_snapshot": {
            "return_24h": 0.01,
            "volume_zscore_24h": 0.1,
            "market_context_freshness_status": "fresh",
        },
    })

    assert result.opportunity_type == "UNCONFIRMED_RESEARCH"
    assert "evidence_acquisition_rejected_results_only" in result.why_not_alertable


def test_event_alpha_source_coverage_coinalyze_links_only_existing_artifacts():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.radar.source_coverage as event_alpha_source_coverage
    import crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight as event_coinalyze_preflight

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        provider_report = event_provider_status.build_event_discovery_provider_status(config)
        report = event_alpha_source_coverage.build_source_coverage_report(
            provider_status_report=provider_report,
            artifact_namespace="unit",
            profile="notify_llm_deep",
            artifact_namespace_dir=base,
            now=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )
        text = event_alpha_source_coverage.format_source_coverage_report(report)
        assert "- Coinalyze preflight: not generated" in text
        assert "event_coinalyze_preflight.md" not in text
        assert "make event-alpha-coinalyze-preflight ARTIFACT_NAMESPACE=unit PROFILE=notify_llm_deep PYTHON=python3" in text

        preflight = event_coinalyze_preflight.build_preflight_report(
            namespace_dir=base,
            smoke_mode=True,
            now=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )
        event_coinalyze_preflight.write_preflight_artifacts(preflight, base)
        report = event_alpha_source_coverage.build_source_coverage_report(
            provider_status_report=provider_report,
            artifact_namespace="unit",
            profile="notify_llm_deep",
            artifact_namespace_dir=base,
            now=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )
        text = event_alpha_source_coverage.format_source_coverage_report(report)
        assert "- Coinalyze preflight report: event_coinalyze_preflight.md" in text
        assert "- Coinalyze preflight JSON: event_coinalyze_preflight.json" in text
        assert "Coinalyze supported metric status:" in text
        assert "basis=fixture_only" in text
        assert report.to_dict()["coinalyze_supported_metric_status"]["predicted_funding"] == "implemented"

        bad = base / "event_alpha_source_coverage.md"
        bad.write_text("- Coinalyze preflight report: event_coinalyze_preflight.md\n- Coinalyze preflight JSON: event_coinalyze_preflight.json\n", encoding="utf-8")
        (base / event_coinalyze_preflight.PREFLIGHT_JSON).unlink()
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            profile="notify_llm_deep",
            artifact_namespace="unit",
            source_coverage_report_path=bad,
            include_test_artifacts=True,
            strict=True,
        )
        assert result.source_coverage_coinalyze_missing_linked_artifact >= 1
        assert result.status == "BLOCKED"
