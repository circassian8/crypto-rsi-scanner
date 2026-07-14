from __future__ import annotations

from pathlib import Path

from crypto_rsi_scanner.event_alpha.dashboard.models import DashboardSnapshot
from crypto_rsi_scanner.event_alpha.dashboard.system_pages import (
    render_campaign_page,
    render_health_page,
    render_outcomes_page,
)


def _snapshot() -> DashboardSnapshot:
    return DashboardSnapshot(
        namespace_dir=Path("/private/tmp/radar/current"),
        run_id="2026-07-14T10:00:00+00:00|no_key_live",
        profile="no_key_live",
        artifact_namespace="radar_market_no_send_current",
        revision=7,
        manifest_status="complete",
        doctor_status="ok",
        doctor_verified_revision=7,
        generation_authority_status="authoritative",
        generation_authority_reasons=(),
        generation_authority_checked_at="2026-07-14T10:05:00+00:00",
        operator_state_sha256="a" * 64,
        operator_state={
            "research_only": True,
            "send_attempted": False,
            "generated_at": "2026-07-14T10:00:00+00:00",
            "artifacts": {
                "market_history": {
                    "path": "event_market_history.jsonl",
                    "status": "complete",
                }
            },
        },
        current_candidates=(
            {
                "candidate_id": "candidate:btc",
                "symbol": "BTC",
                "_decision_model_status": "v2",
                "_dashboard_route": "dashboard_watch",
            },
        ),
        current_market_anomalies=(
            {"symbol": "BTC", "anomaly_type": "volume_expansion"},
        ),
        current_market_observations=(
            {
                "symbol": "BTC",
                "freshness_status": "fresh",
                "spread_status": "unavailable",
                "market_data_quality": {"baseline_status": "warming"},
            },
            {
                "symbol": "ETH",
                "freshness_status": "fresh",
                "spread_status": "unavailable",
                "market_data_quality": {"baseline_status": "cold"},
            },
        ),
        exact_market_history=(),
        exact_market_history_metadata={
            "authority": "current_generation_fingerprint_verified",
            "sha256": "b" * 64,
        },
        current_calendar_events=(),
        current_outcomes=(
            {
                "candidate_id": "candidate:btc",
                "symbol": "BTC",
                "outcome_status": "pending",
                "radar_route": "dashboard_watch",
                "observed_at": "2026-07-14T10:00:00+00:00",
                "preferred_horizon": "24h",
                "actionability_score_cohort": "50_69",
                "evidence_confidence_score_cohort": "25_49",
                "risk_score_cohort": "25_44",
                "research_only": True,
            },
            {
                "candidate_id": "candidate:eth",
                "symbol": "ETH",
                "outcome_status": "matured",
                "radar_route": "risk_watch",
                "observed_at": "2026-07-13T10:00:00+00:00",
                "outcome_evaluated_at": "2026-07-14T09:00:00+00:00",
                "primary_horizon": "24h",
                "actionability_score_cohort": "25_49",
                "evidence_confidence_score_cohort": "50_69",
                "risk_score_cohort": "65_100",
                "outcome_label": "thesis_confirmed",
                "research_only": True,
            },
        ),
        current_outcomes_metadata={
            "authority": "current_generation_fingerprint_verified",
            "sha256": "c" * 64,
        },
        current_request_ledger={
            "provider": "coingecko",
            "live_provider_authorized": True,
            "provider_call_attempted": True,
            "provider_request_succeeded": True,
            "http_status": 200,
            "request_started_at": "2026-07-14T10:00:00+00:00",
            "request_ended_at": "2026-07-14T10:00:01.500000+00:00",
            "duration_ms": 1500,
            "result_count": 80,
            "selected_market_row_count": 2,
            "raw_market_row_count": 80,
            "retry_count": 0,
            "cache_behavior": "network",
            "candidate_source_mode": "live_no_send",
            "observed_at": "2026-07-14T10:00:00+00:00",
            "no_send": True,
            "telegram_sends": 0,
            "trades_created": 0,
            "paper_trades_created": 0,
            "normal_rsi_signal_rows_written": 0,
            "triggered_fade_created": 0,
        },
        current_request_ledger_metadata={
            "authority": "current_generation_fingerprint_verified",
            "sha256": "d" * 64,
        },
        source_coverage={
            "packs": [
                {
                    "source_pack": "market_anomaly_pack",
                    "provider_coverage_status": "observed_healthy",
                    "accepted_evidence_count": 2,
                    "healthy_providers": ["coingecko"],
                },
                {
                    "source_pack": "unlock_supply_pack",
                    "provider_coverage_status": "not_configured",
                    "accepted_evidence_count": 0,
                    "missing_providers": ["tokenomist"],
                    "coverage_gap_reason": "missing_provider_configuration",
                },
            ]
        },
        market_generation={
            "status": "complete",
            "provider": "coingecko",
            "candidate_source_mode": "live_no_send",
            "live_provider_authorized": True,
            "provider_request_succeeded": True,
            "raw_market_row_count": 80,
            "selected_market_row_count": 2,
            "core_row_count": 1,
            "card_count": 1,
            "decision_radar_campaign_counted": True,
            "observed_at": "2026-07-14T10:00:00+00:00",
            "market_provenance": {
                "data_quality": {
                    "direct_feature_count": 12,
                    "proxy_feature_count": 5,
                },
                "feature_basis": {
                    "returns": "provider_derived_sparkline",
                    "volume_zscore_24h": "cross_sectional_log_turnover_proxy",
                    "liquidity": "coingecko_total_volume_24h_proxy",
                    "spread": "unavailable",
                },
            },
        },
        cumulative_feedback=(
            {"feedback_label": "useful"},
            {"feedback_label": "watch"},
        ),
        cumulative_outcomes=(
            {
                "artifact_namespace": "older_namespace",
                "candidate_id": "candidate:sol",
                "symbol": "SOL",
                "outcome_status": "matured",
                "radar_route": "actionable_watch",
                "observed_at": "2026-07-10T10:00:00+00:00",
                "outcome_evaluated_at": "2026-07-11T10:00:00+00:00",
                "outcome_label": "thesis_invalidated",
            },
        ),
        campaign_outcomes=(
            {
                "artifact_namespace": "campaign_namespace",
                "candidate_id": "candidate:dexe",
                "symbol": "DEXE",
                "outcome_status": "pending",
                "radar_route": "risk_watch",
                "observed_at": "2026-07-13T15:00:00+00:00",
                "actionability_score": 35,
                "evidence_confidence_score": 45,
                "risk_score": 70,
            },
        ),
        campaign_attempts=(
            {
                "attempt_id": "complete-attempt",
                "recorded_at": "2026-07-13T19:07:30+00:00",
                "observed_at": "2026-07-13T19:07:29+00:00",
                "artifact_namespace": "complete-space",
                "run_id": "complete-run",
                "status": "complete",
                "provider": "coingecko",
                "candidate_source_mode": "live_no_send",
                "provider_call_attempted": True,
                "provider_request_succeeded": True,
                "decision_radar_campaign_counted": True,
            },
            {
                "attempt_id": "failed-attempt",
                "recorded_at": "2026-07-14T08:00:00+00:00",
                "observed_at": "2026-07-14T08:00:00+00:00",
                "artifact_namespace": "failed-space",
                "run_id": "failed-run",
                "status": "failed",
                "provider": "example_feed",
                "candidate_source_mode": "live_no_send",
                "provider_call_attempted": True,
                "provider_request_succeeded": False,
                "decision_radar_campaign_counted": False,
                "failure_class": "provider_timeout",
            },
        ),
        campaign_latest_attempt={
            "attempt_id": "complete-attempt",
            "recorded_at": "2026-07-13T19:07:30+00:00",
            "observed_at": "2026-07-13T19:07:29+00:00",
            "artifact_namespace": "complete-space",
            "run_id": "complete-run",
            "status": "complete",
            "provider": "coingecko",
            "provider_call_attempted": True,
            "provider_request_succeeded": True,
            "decision_radar_campaign_counted": True,
        },
        campaign_reservation={
            "artifact_namespace": "radar_market_no_send_current",
            "status": "released",
            "acquired_at": "2026-07-14T10:00:00+00:00",
            "expires_at": "2026-07-14T10:15:00+00:00",
            "provider_call_reserved_at": "2026-07-14T10:00:00+00:00",
            "released_at": "2026-07-14T10:00:02+00:00",
            "next_provider_call_at": "2026-07-14T11:00:00+00:00",
            "no_send": True,
        },
        campaign_history_metadata={
            "event_market_no_send_attempts.jsonl": {
                "authority": "historical_non_authoritative",
                "source_row_count": 2,
                "returned_row_count": 2,
                "error": None,
                "sha256": "e" * 64,
            }
        },
        cumulative_history_metadata={},
        provider_readiness={
            "providers": [
                {
                    "provider": "good_provider",
                    "configured": True,
                    "enabled_by_default": True,
                    "live_call_allowed": True,
                    "status": "healthy",
                    "last_success_at": "2026-07-14T09:55:00+00:00",
                },
                {
                    "provider": "disabled_feed",
                    "configured": True,
                    "enabled_by_default": False,
                    "live_call_allowed": False,
                    "status": "config_ready_no_live",
                },
                {
                    "provider": "needs_auth",
                    "configured": False,
                    "status": "missing_authorization",
                    "reason": "api_key_missing",
                },
                {
                    "provider": "broken_feed",
                    "configured": True,
                    "enabled_by_default": True,
                    "live_call_allowed": True,
                    "status": "degraded",
                    "http_status": 429,
                    "error_class": "rate_limited",
                },
                {
                    "provider": "warming_feed",
                    "configured": True,
                    "enabled_by_default": True,
                    "live_call_allowed": True,
                    "status": "warming",
                },
            ]
        },
        provider_health={
            "providers": [
                {
                    "provider": "historical_feed",
                    "status": "observed_healthy",
                }
            ]
        },
        provider_health_read_at="2026-07-14T10:05:00+00:00",
        provider_health_sha256="f" * 64,
    )


def test_health_page_distinguishes_failures_disabled_setup_and_warming() -> None:
    page = render_health_page(_snapshot())

    assert "Actual provider failures need review" in page
    assert "Provider failure" in page
    assert "Actual provider failure." in page
    assert "HTTP 429" in page
    assert "Disabled / not selected" in page
    assert "not a request failure" in page
    assert "Authorization missing" in page
    assert "No request was expected" in page
    assert "Warming" in page
    assert "Temporal evidence is still warming" in page
    assert "rate_limited" not in page


def test_health_page_exposes_exact_contract_request_quality_and_coverage() -> None:
    page = render_health_page(_snapshot())

    assert "Exact operator generation" in page
    assert "Pointer / publication authority" in page
    assert "Trusted" not in page  # The exact status is authoritative, not marketing copy.
    assert "Doctor verified revision" in page
    assert "Provider request" in page
    assert "Authorization present" in page
    assert "HTTP 200" in page
    assert "1 min" not in page
    assert "1.5 sec" not in page  # Duration intentionally uses concise whole-unit display.
    assert "2 sec" in page
    assert "Telegram sends 0" in page
    assert "Market data quality" in page
    assert "12" in page and "5" in page
    assert "Spread verified" in page
    assert "Source-pack coverage" in page
    assert "Market anomaly pack" in page
    assert "Coverage is not absence" in page


def test_health_page_keeps_portable_identity_and_hashes_in_collapsed_technical_sections() -> None:
    page = render_health_page(_snapshot())

    details_at = page.index("<details")
    namespace_at = page.index("<dd>radar_market_no_send_current</dd>", details_at)
    hash_at = page.index("a" * 64)
    assert "/private/tmp/radar/current" not in page
    assert namespace_at > details_at
    assert hash_at > details_at
    assert "Paths and fingerprints" in page
    assert "Historical / non-authoritative" in page


def test_outcomes_page_separates_exact_current_from_historical_learning() -> None:
    page = render_outcomes_page(_snapshot(), {})

    assert "Exact current-generation outcomes" in page
    assert "Fingerprint-verified placeholders" in page
    assert "Historical campaign outcomes" in page
    assert "Historical / non-authoritative" in page
    assert "BTC" in page and "ETH" in page
    assert "SOL" in page and "DEXE" in page
    assert "Pending" in page
    assert "Matured" in page
    assert "Risk watch" in page
    assert "50–69" in page
    assert "Small-sample warning" in page
    assert "Do not infer edge or change thresholds" in page


def test_outcomes_filters_scope_status_route_and_search_without_reclassification() -> None:
    page = render_outcomes_page(
        _snapshot(),
        {
            "scope": "current",
            "status": "pending",
            "route": "dashboard_watch",
            "search": "btc",
        },
    )

    assert "BTC" in page
    assert "ETH" not in page
    assert "Historical campaign outcomes" not in page
    assert 'option value="current" selected' in page
    assert 'option value="pending" selected' in page
    assert 'value="dashboard_watch"' in page


def test_outcomes_feedback_is_optional_and_never_presented_as_threshold_control() -> None:
    page = render_outcomes_page(_snapshot(), {"scope": "historical"})

    assert "Optional human feedback" in page
    assert "Useful" in page
    assert "Watch" in page
    assert "does not automatically change scores, routes, gates, or visibility" in page
    assert "Exact current-generation outcomes" not in page


def test_campaign_page_leads_with_exact_current_authority_and_full_run_context() -> None:
    page = render_campaign_page(_snapshot(), {})

    assert "Current authoritative generation" in page
    assert "Current pointer" in page
    assert "radar_market_no_send_current" in page
    assert "2026-07-14T10:00:00+00:00|no_key_live" in page
    assert "Revision" in page
    assert "CoinGecko" in page
    assert "Authorization present" in page
    assert "Live / real data · no-send" in page
    assert "Observations / anomalies / ideas" in page
    assert "2 / 1 / 1" in page
    assert "12 / 5" in page
    assert "Strict doctor" in page
    assert "Publication" in page


def test_campaign_page_labels_attempts_historical_and_humanizes_failure() -> None:
    page = render_campaign_page(_snapshot(), {})

    assert "Bounded attempt ledger" in page
    assert "Historical / non-authoritative" in page
    assert "complete-space" in page
    assert "failed-space" in page
    assert "Provider timeout." in page
    assert "provider_timeout" not in page
    assert 'class="table-scroll"' in page
    assert 'data-label="Provider"' in page


def test_campaign_filters_are_bounded_to_loaded_attempt_rows() -> None:
    page = render_campaign_page(
        _snapshot(),
        {"status": "failed", "provider": "example_feed", "search": "failed-space"},
    )

    ledger_section = page.split("Bounded attempt ledger", 1)[1]
    assert "failed-space" in ledger_section
    assert "complete-space" not in ledger_section
    assert 'value="failed"' in page
    assert 'value="example_feed"' in page


def test_campaign_page_shows_latest_reservation_next_eligibility_and_collapsed_metadata() -> None:
    page = render_campaign_page(_snapshot(), {})

    assert "Latest attempt receipt" in page
    assert "Cadence and reservation" in page
    assert "Next provider-call eligibility" in page
    assert 'datetime="2026-07-14T11:00:00Z"' in page
    assert "No-send" in page
    assert "Campaign artifact evidence" in page
    assert "Historical bounds, errors, and fingerprints" in page
    assert "<details" in page
    assert "e" * 64 in page


def test_system_pages_escape_untrusted_display_values() -> None:
    snapshot = _snapshot()
    snapshot.provider_readiness["providers"][0]["provider"] = '<script>alert("x")</script>'
    snapshot.campaign_attempts[1]["artifact_namespace"] = "<b>bad</b>"

    health = render_health_page(snapshot)
    campaign = render_campaign_page(snapshot, {})

    assert "<script>" not in health
    assert "&lt;script&gt;" in health
    assert "<b>bad</b>" not in campaign
    assert "&lt;b&gt;bad&lt;/b&gt;" in campaign
