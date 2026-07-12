"""Artifact-doctor provider-conflict and integrated safety regressions."""

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from types import SimpleNamespace

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_alpha_bybit_announcements_rehearsal_mocked_429_403_and_doctor_conflicts_are_safe():
    import json
    from datetime import datetime, timezone
    from io import BytesIO
    from urllib.error import HTTPError

    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight as event_bybit_announcements_preflight

    original_max_pages = os.environ.get(event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES)
    original_allow = os.environ.get(event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT)
    try:
        os.environ[event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES] = "1"
        os.environ[event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT] = "1"

        def raising_opener(code, body=b"", headers=None):
            def opener(request, _timeout):
                raise HTTPError(request.full_url, code, "blocked", headers or {}, BytesIO(body))

            return opener

        cases = (
            (429, b"", {}, "rate_limited"),
            (401, b"", {}, "auth_or_access_error"),
            (
                403,
                b"access too frequent",
                {"Retry-After": "600", "Set-Cookie": "private-cookie"},
                "rate_limited",
            ),
            (
                403,
                b'{"retCode":10009,"retMsg":"Service Restricted: unavailable for your region"}',
                {"Content-Type": "application/json", "Server": "edge"},
                "region_restricted",
            ),
            (
                403,
                b"The Amazon CloudFront distribution is configured to block access from your country",
                {"Content-Type": "text/plain", "X-Amz-Cf-Id": "safe-request-id"},
                "region_restricted",
            ),
            (
                403,
                b"<html><body>generic edge denial for 203.0.113.10 token=private-value "
                + (b"x" * 3_000)
                + b"</body></html>",
                {"Content-Type": "text/html", "CF-Ray": "safe-ray"},
                "edge_forbidden",
            ),
        )
        for code, body, headers, expected_status in cases:
            with TemporaryDirectory() as tmp:
                base = Path(tmp)
                _preflight, report, _paths = event_bybit_announcements_preflight.run_no_send_rehearsal(
                    namespace_dir=base,
                    provider_health_path=base / "event_provider_health.json",
                    profile="fixture",
                    artifact_namespace="bybit_error_mock",
                    allow_live_preflight=True,
                    opener=raising_opener(code, body, headers),
                    now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
                )
                ledger_text = (base / event_bybit_announcements_preflight.REQUEST_LEDGER).read_text(encoding="utf-8")
                ledger_rows = [json.loads(line) for line in ledger_text.splitlines() if line.strip()]
                assert report.status == expected_status
                assert report.provider_health_status == expected_status
                assert ledger_rows[0]["status_code"] == code
                assert ledger_rows[0]["success"] is False
                assert ledger_rows[0]["request_id"]
                assert len(ledger_rows[0]["request_id"]) == 32
                assert "set-cookie" not in ledger_rows[0]["response_headers_safe"]
                assert ledger_rows[0]["response_bytes_captured"] <= 2048
                summary = ledger_rows[0]["response_body_summary_redacted"]
                assert summary is None or len(summary) <= 320
                assert ledger_rows[0]["response_body_truncated"] is (len(body) > 2048)
                assert "Authorization" not in ledger_text
                assert "api_key" not in ledger_text.casefold()
                assert "private-cookie" not in ledger_text
                assert "private-value" not in ledger_text
                assert "203.0.113.10" not in ledger_text

        class RegionResponse:
            status = 200
            headers = {"Content-Type": "application/json", "Set-Cookie": "private-cookie"}

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _tb):
                return False

            def read(self):
                return b'{"retCode":10009,"retMsg":"Service Restricted"}'

        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _preflight, report, _paths = event_bybit_announcements_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="fixture",
                artifact_namespace="bybit_region_json_mock",
                allow_live_preflight=True,
                opener=lambda _request, _timeout: RegionResponse(),
                now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
            )
            ledger_rows = [
                json.loads(line)
                for line in (base / event_bybit_announcements_preflight.REQUEST_LEDGER).read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            assert report.status == "region_restricted"
            assert report.provider_health_status == "region_restricted"
            assert ledger_rows[0]["status_code"] == 200
            assert ledger_rows[0]["success"] is False
            assert ledger_rows[0]["error_class"] == "BybitAPIResponseError"
            assert "10009" in ledger_rows[0]["response_body_summary_redacted"]
            assert "set-cookie" not in ledger_rows[0]["response_headers_safe"]
            assert "private-cookie" not in json.dumps(ledger_rows[0])

        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / event_bybit_announcements_preflight.REHEARSAL_JSON).write_text(
                json.dumps({
                    "provider": "bybit_announcements",
                    "live_call_allowed": True,
                    "allow_live_preflight": False,
                    "telegram_sends": 1,
                }),
                encoding="utf-8",
            )
            (base / event_bybit_announcements_preflight.REQUEST_LEDGER).write_text(
                json.dumps({
                    "provider": "bybit_announcements",
                    "live_call_allowed": True,
                    "unsupported_query_params": ["category"],
                })
                + "\n",
                encoding="utf-8",
            )
            conflicts = event_bybit_announcements_preflight.artifact_conflicts(base)
            assert conflicts["bybit_announcements_rehearsal_live_without_explicit_allow"] == 1
            assert conflicts["bybit_announcements_rehearsal_unsupported_params"] == 1
            assert conflicts["bybit_announcements_rehearsal_forbidden_side_effect_claim"] == 1
            doctor = event_alpha_artifact_doctor.diagnose_artifacts(
                inspected_alert_store_path=base / "event_alpha_alerts.jsonl",
                profile="fixture",
                artifact_namespace="bybit_error_mock",
                include_test_artifacts=True,
                strict=True,
            )
            assert doctor.bybit_announcements_rehearsal_live_without_explicit_allow == 1
            assert doctor.bybit_announcements_rehearsal_unsupported_params == 1
            assert doctor.bybit_announcements_rehearsal_forbidden_side_effect_claim == 1
            assert doctor.status == "BLOCKED"
    finally:
        if original_max_pages is None:
            os.environ.pop(event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES, None)
        else:
            os.environ[event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES] = original_max_pages
        if original_allow is None:
            os.environ.pop(event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT, None)
        else:
            os.environ[event_bybit_announcements_preflight.ENV_ALLOW_LIVE_PREFLIGHT] = original_allow


def test_official_exchange_artifact_doctor_conflicts():
    import json

    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.providers.official_exchange_activation as event_official_exchange_activation

    rows = [
        {
            "row_type": "official_listing_candidate",
            "symbol": "BAD",
            "coin_id": "bad",
            "event_type": "spot_listing",
            "source_class": "crypto_news",
            "source_pack": "official_exchange_listing_pack",
            "title": "Media says BAD listed",
            "published_at": "2026-06-15T12:00:00Z",
            "source_url": "https://example.test/bad",
        },
        {
            "row_type": "official_listing_candidate",
            "symbol": "USDT",
            "coin_id": "tether",
            "event_type": "spot_listing",
            "source_class": "official_exchange",
            "source_pack": "official_exchange_listing_pack",
            "title": "Binance Adds BTC/USDT",
            "published_at": "2026-06-15T12:00:00Z",
            "source_url": "https://www.binance.com/en/support/announcement/btc-usdt",
        },
        {
            "row_type": "official_listing_candidate",
            "symbol": "DLST",
            "coin_id": "delist",
            "event_type": "delisting",
            "source_class": "official_exchange",
            "source_pack": "official_exchange_risk_pack",
            "title": "Binance Will Delist DLST",
            "published_at": "2026-06-15T12:00:00Z",
            "source_url": "https://www.binance.com/en/support/announcement/dlst",
            "opportunity_type": "CONFIRMED_LONG_RESEARCH",
        },
        {
            "row_type": "official_listing_candidate",
            "symbol": "MISS",
            "coin_id": "missing",
            "event_type": "spot_listing",
            "source_class": "official_exchange",
            "source_pack": "official_exchange_listing_pack",
        },
        {
            "row_type": "official_listing_candidate",
            "symbol": "LEAK",
            "coin_id": "leak",
            "event_type": "spot_listing",
            "source_class": "official_exchange",
            "source_pack": "official_exchange_listing_pack",
            "title": "Binance Will List LEAK",
            "published_at": "2026-06-15T12:00:00Z",
            "source_url": "https://www.binance.com/en/support/announcement/leak?signature=abc",
        },
        {
            "row_type": "official_listing_candidate",
            "symbol": "ALRT",
            "coin_id": "alert",
            "event_type": "spot_listing",
            "source_class": "official_exchange",
            "source_pack": "official_exchange_listing_pack",
            "title": "Binance Will List ALRT",
            "published_at": "2026-06-15T12:00:00Z",
            "source_url": "https://www.binance.com/en/support/announcement/alrt",
            "created_alert": True,
        },
        {
            "row_type": "official_listing_candidate",
            "symbol": "BTC",
            "coin_id": "bitcoin",
            "event_type": "spot_listing",
            "source_class": "official_exchange",
            "source_pack": "official_exchange_listing_pack",
            "title": "Bybit Adds BTC/USDT",
            "published_at": "2026-06-15T12:00:00Z",
            "source_url": "https://announcements.bybit.com/article/btc-usdt",
            "major_pair_simple_announcement": True,
            "opportunity_type": "EARLY_LONG_RESEARCH",
        },
    ]
    conflicts = event_alpha_artifact_doctor._official_exchange_artifact_conflicts(rows)

    assert conflicts["official_exchange_listing_without_official_source"] == 1
    assert conflicts["official_exchange_quote_asset_misclassified"] == 1
    assert conflicts["official_exchange_delisting_long_research"] == 1
    assert conflicts["official_exchange_candidate_missing_source_fields"] == 1
    assert conflicts["official_exchange_secret_leak"] == 1
    assert conflicts["official_exchange_major_pair_noise_promoted_early_long"] == 1
    assert conflicts["official_exchange_created_alert_rows"] == 1

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / event_official_exchange_activation.ACTIVATION_JSON).write_text(
            json.dumps(
                {
                    "schema_version": "event_official_exchange_activation_v1",
                    "providers": [
                        {
                            "provider": "bybit_announcements_public",
                            "mode": "public_http_no_key",
                            "configured": True,
                            "live_call_allowed": True,
                            "no_send_rehearsal": True,
                            "request_ledger_path": None,
                            "provider_health_key": "bybit_announcements",
                            "source_url_count": 1,
                            "announcements_seen": 1,
                            "official_events_written": 1,
                            "listing_candidates_written": 1,
                            "risk_candidates_written": 0,
                            "strict_alerts_created": 0,
                            "telegram_sends": 1,
                        },
                        {
                            "provider": "binance_announcements_signed_listener",
                            "mode": "signed_websocket_listener",
                            "configured": True,
                            "live_call_allowed": False,
                            "no_send_rehearsal": True,
                            "request_ledger_path": None,
                            "provider_health_key": "binance_announcements_signed_listener",
                            "source_url_count": 0,
                            "announcements_seen": 0,
                            "official_events_written": 0,
                            "listing_candidates_written": 0,
                            "risk_candidates_written": 0,
                            "strict_alerts_created": 0,
                            "telegram_sends": 0,
                            "last_error_safe": "api_secret='THIS_IS_A_TEST_SECRET_VALUE_123456'",
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        activation_conflicts = event_official_exchange_activation.artifact_conflicts(base)
        assert activation_conflicts["official_exchange_activation_live_without_ledger"] == 1
        assert activation_conflicts["official_exchange_activation_signed_listener_secret_leak"] == 1
        assert activation_conflicts["official_exchange_activation_forbidden_side_effect_claim"] == 1
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            inspected_alert_store_path=base / "event_alpha_alerts.jsonl",
            profile="fixture",
            artifact_namespace="official_exchange_smoke",
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor.official_exchange_activation_live_without_ledger == 1
        assert doctor.official_exchange_activation_signed_listener_secret_leak == 1
        assert doctor.official_exchange_activation_forbidden_side_effect_claim == 1
        assert doctor.status == "BLOCKED"


def test_scheduled_catalyst_artifact_doctor_conflicts():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    rows = [
        {
            "row_type": "unlock_event",
            "symbol": "MEDIA",
            "coin_id": "media",
            "event_type": "token_unlock",
            "impact_path_type": "unlock_supply_event",
            "source_class": "cryptopanic_tagged",
            "source_url": "https://cryptopanic.com/news/media",
            "unlock_time": "2026-06-16T16:00:00Z",
            "unlock_pct_circulating_supply": 0.12,
            "opportunity_type": "RISK_ONLY",
        },
        {
            "row_type": "unlock_event",
            "symbol": "MISS",
            "coin_id": "missing",
            "event_type": "token_unlock",
            "source_class": "structured_unlock",
            "source_url": "https://tokenomist.ai/miss",
            "opportunity_type": "RISK_ONLY",
        },
        {
            "row_type": "unlock_event",
            "symbol": "SIZE",
            "coin_id": "size",
            "event_type": "token_unlock",
            "source_class": "structured_unlock",
            "source_url": "https://tokenomist.ai/size",
            "unlock_time": "2026-06-16T16:00:00Z",
            "opportunity_type": "FADE_SHORT_REVIEW",
        },
        {
            "row_type": "scheduled_catalyst_event",
            "symbol": "STALE",
            "coin_id": "stale",
            "event_type": "protocol_upgrade",
            "event_status": "completed",
            "event_age_hours": 48,
            "source_url": "https://project.test/stale",
            "opportunity_type": "EARLY_LONG_RESEARCH",
        },
        {
            "row_type": "scheduled_catalyst_event",
            "symbol": "NOSRC",
            "coin_id": "nosrc",
            "event_type": "protocol_upgrade",
            "opportunity_type": "EARLY_LONG_RESEARCH",
        },
        {
            "row_type": "scheduled_catalyst_event",
            "symbol": "ALRT",
            "coin_id": "alert",
            "event_type": "protocol_upgrade",
            "source_url": "https://project.test/alert",
            "created_alert": True,
        },
    ]
    conflicts = event_alpha_artifact_doctor._scheduled_catalyst_artifact_conflicts(rows)

    assert conflicts["unlock_without_structured_evidence"] == 1
    assert conflicts["media_unlock_promoted_structured"] == 1
    assert conflicts["cryptopanic_unlock_proof"] == 1
    assert conflicts["unlock_missing_event_time"] == 1
    assert conflicts["unlock_promoted_without_size_metrics"] == 2
    assert conflicts["stale_completed_catalyst_upcoming"] == 1
    assert conflicts["calendar_event_missing_source_url"] == 1
    assert conflicts["scheduled_catalyst_created_alert_rows"] == 1


def test_derivatives_crowding_artifact_doctor_conflicts():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    rows = [
        {
            "row_type": "derivatives_state_snapshot",
            "symbol": "MISS",
            "funding_rate": 0.001,
            "supported_metric_status": {"basis": "implemented"},
            "raw_payload_redacted": {"api_key": "should_not_show"},
        },
        {
            "row_type": "fade_short_review_candidate",
            "symbol": "NOMOVE",
            "opportunity_type": "FADE_SHORT_REVIEW",
            "completed_move": False,
            "fade_requirements_met": True,
            "crowding_exhaustion_evidence": ["funding_zscore_elevated"],
            "research_only_disclaimer": "Research-only. Not a trade signal.",
            "derivatives_state_snapshot": {"freshness_status": "stale"},
        },
        {
            "row_type": "fade_short_review_candidate",
            "symbol": "NOCROWD",
            "opportunity_type": "FADE_SHORT_REVIEW",
            "completed_move": True,
            "fade_requirements_met": False,
            "crowding_exhaustion_evidence": [],
            "research_only_disclaimer": "Research-only. Not a trade signal.",
        },
        {
            "row_type": "fade_short_review_candidate",
            "symbol": "LEAK",
            "opportunity_type": "FADE_SHORT_REVIEW",
            "completed_move": True,
            "fade_requirements_met": True,
            "crowding_exhaustion_evidence": ["funding_zscore_elevated"],
            "research_only_disclaimer": "fade review",
            "triggered_fade_created": True,
            "normal_rsi_signal_written": True,
            "raw_payload_redacted": {"auth_token": "abc"},
        },
        {
            "row_type": "fade_short_review_candidate",
            "symbol": "CROWDLONG",
            "opportunity_type": "CONFIRMED_LONG_RESEARCH",
            "crowding_class": "high",
            "warnings": [],
            "research_only_disclaimer": "Research-only. Not a trade signal.",
        },
    ]
    conflicts = event_alpha_artifact_doctor._derivatives_crowding_artifact_conflicts(rows)

    assert conflicts["fade_review_without_completed_move"] == 1
    assert conflicts["fade_review_without_crowding_exhaustion"] == 1
    assert conflicts["fade_review_created_triggered_fade"] == 1
    assert conflicts["fade_review_created_normal_rsi_signal"] == 1
    assert conflicts["fade_review_notification_missing_disclaimer"] == 1
    assert conflicts["derivatives_artifact_secret_leak"] == 2
    assert conflicts["derivatives_state_missing_freshness_status"] == 1
    assert conflicts["derivatives_metric_claim_implemented_missing"] == 1
    assert conflicts["derivatives_unit_metadata_missing"] == 1
    assert conflicts["stale_derivatives_snapshot_promoted_fade_review"] == 1
    assert conflicts["confirmed_long_crowded_without_warning"] == 1


def test_instrument_resolution_artifact_doctor_conflicts():
    import json

    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.radar.asset_registry as event_asset_registry
    import crypto_rsi_scanner.event_alpha.radar.instrument_resolver as event_instrument_resolver

    with TemporaryDirectory() as tmp:
        namespace = Path(tmp)
        registry = event_asset_registry.build_asset_registry(fixture_path=config.EVENT_ASSET_REGISTRY_PATH)
        event_asset_registry.write_asset_registry_artifact(
            registry,
            namespace,
            generated_at="2026-06-15T16:00:00Z",
            profile="fixture",
            artifact_namespace="instrument_resolution_test",
            run_mode="fixture",
            run_id="run",
        )
        bad_candidates = [
            {
                "row_type": "event_integrated_radar_candidate",
                "symbol": "TESTPERP",
                "coin_id": "test-perp",
                "opportunity_type": "CONFIRMED_LONG_RESEARCH",
            },
            {
                "row_type": "event_integrated_radar_candidate",
                "symbol": "USDT",
                "coin_id": "tether",
                "canonical_asset_id": "tether",
                "opportunity_type": "EARLY_LONG_RESEARCH",
                "is_tradable_asset": True,
                "quote_asset_excluded": True,
            },
            {
                "row_type": "event_integrated_radar_candidate",
                "symbol": "SECTOR",
                "coin_id": "ai_theme",
                "canonical_asset_id": "ai_theme",
                "opportunity_type": "CONFIRMED_LONG_RESEARCH",
                "is_tradable_asset": True,
                "is_theme_or_sector": True,
            },
        ]
        (namespace / "event_integrated_radar_candidates.jsonl").write_text(
            "\n".join(json.dumps(row) for row in bad_candidates) + "\n",
            encoding="utf-8",
        )
        (namespace / event_instrument_resolver.INSTRUMENT_RESOLUTION_JSONL).write_text(
            json.dumps({
                "row_type": "event_instrument_resolution",
                "resolver_warnings": ["coinalyze_symbol_not_linked_to_asset"],
            })
            + "\n",
            encoding="utf-8",
        )

        conflicts = event_instrument_resolver.artifact_conflicts(namespace)
        assert conflicts["instrument_resolution_missing_canonical_id_when_fixture_has_it"] == 1
        assert conflicts["instrument_resolution_quote_asset_misclassified"] == 1
        assert conflicts["instrument_resolution_sector_visible_as_tradable"] == 1
        assert conflicts["instrument_resolution_coinalyze_symbol_unlinked"] == 1


def test_integrated_doctor_catches_core_and_card_mismatches():
    import json

    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    candidate = {
        "row_type": "event_integrated_radar_candidate",
        "symbol": "BTC",
        "core_opportunity_id": "core-btc",
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "market_state_class": "no_reaction",
        "source_url": "https://example.com/btc",
        "reason_codes": ["major_pair_simple_announcement_capped"],
        "major_pair_simple_announcement": True,
        "why_now": "simple major-pair announcement capped as unconfirmed research",
        "official_exchange_event": {"event_type": "new_trading_pair", "exchange": "binance", "source_url": "https://example.com/btc"},
    }
    core = {
        "core_opportunity_id": "core-btc",
        "symbol": "BTC",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "market_state_class": "confirmed_breakout",
        "reason_codes": [],
    }

    conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
        [candidate],
        core_rows=[core],
        research_card_paths=(),
    )

    assert conflicts["integrated_candidate_core_opportunity_type_mismatch"] == 1
    assert conflicts["integrated_candidate_core_market_state_mismatch"] == 1
    assert conflicts["integrated_candidate_core_reason_code_loss"] == 1
    assert conflicts["integrated_candidate_core_source_url_loss"] == 1
    assert conflicts["integrated_candidate_core_official_event_loss"] == 1
    assert conflicts["integrated_core_silent_upgrade"] == 1

    with TemporaryDirectory() as tmp:
        bad_card = Path(tmp) / "card_core_btc.md"
        bad_card.write_text(
            "\n".join([
                "# BTC Event Research Card",
                "",
                "## Opportunity Lane",
                "- Opportunity type: EARLY_LONG_RESEARCH",
                "- Why now: strong source with no reaction; monitor before the move is crowded",
                "",
                "## Artifact Lineage",
                "- Core opportunity ID: core-btc",
            ]),
            encoding="utf-8",
        )
        card_conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
            [candidate],
            core_rows=[{**candidate, "row_type": "event_core_opportunity"}],
            research_card_paths=(bad_card,),
        )
    assert card_conflicts["integrated_candidate_card_opportunity_type_mismatch"] == 1
    assert card_conflicts["card_opportunity_lane_core_mismatch"] == 1
    assert card_conflicts["integrated_candidate_card_why_now_mismatch"] == 1
    assert card_conflicts["integrated_major_pair_card_early_long"] == 1
    assert card_conflicts["integrated_card_generic_lane_override"] == 1

    fade_candidate = {
        "row_type": "event_integrated_radar_candidate",
        "symbol": "TESTFADE",
        "core_opportunity_id": "core-fade",
        "opportunity_type": "FADE_SHORT_REVIEW",
        "market_state_class": "post_event_fade_setup",
        "market_requirements_met": True,
        "derivatives_state_snapshot": {"funding_rate": 0.12},
        "crowding_class": "extreme",
        "fade_readiness": "ready_for_review",
        "crowding_exhaustion_evidence": ["open_interest_delta_24h_high"],
    }
    with TemporaryDirectory() as tmp:
        bad_fade_card = Path(tmp) / "card_core_fade.md"
        bad_fade_card.write_text(
            "\n".join([
                "# TESTFADE Event Research Card",
                "",
                "## Opportunity Lane",
                "- Opportunity type: FADE_SHORT_REVIEW",
                "- Why now: completed move with derivatives crowding/exhaustion evidence",
                "",
                "## Derivatives / Crowding",
                "- Funding: current=+12.00% predicted=n/a z=n/a",
                "- Basis: n/a unit=unknown",
                "- Crowding class: unknown",
                "- Fade readiness: unknown",
                "",
                "## Outcome Tracking",
                "- Asset primary return: -12.00%",
                "",
                "## Artifact Lineage",
                "- Core opportunity ID: core-fade",
            ]),
            encoding="utf-8",
        )
        fade_conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
            [fade_candidate],
            core_rows=[{**fade_candidate, "row_type": "event_core_opportunity"}],
            research_card_paths=(bad_fade_card,),
        )
    assert fade_conflicts["integrated_fade_card_missing_disclaimer"] == 1
    assert fade_conflicts["integrated_fade_card_crowding_unknown"] == 1
    assert fade_conflicts["derivatives_card_metric_claim_without_data"] == 2
    assert fade_conflicts["integrated_outcome_card_thesis_interpretation_missing"] == 1

    coinalyze_candidate = {
        "row_type": "event_integrated_radar_candidate",
        "symbol": "TESTPERP",
        "core_opportunity_id": "core-perp",
        "opportunity_type": "CONFIRMED_LONG_RESEARCH",
        "market_state_class": "confirmed_breakout",
        "source_requirements_met": True,
        "market_requirements_met": True,
        "coinalyze_derivatives_attached": True,
        "coinalyze_artifact_namespace": "external_coinalyze",
        "derivatives_state_snapshot": {
            "provider": "coinalyze",
            "coinalyze_artifact_namespace": "external_coinalyze",
            "coinalyze_source_artifact_path": "event_fade_cache/external_coinalyze/event_derivatives_state.jsonl",
            "funding_rate": 0.0008,
            "freshness_status": "fresh",
        },
        "crowding_class": "high",
        "crowding_exhaustion_evidence": ["open_interest_delta_24h_high"],
    }
    with TemporaryDirectory() as tmp:
        missing_coinalyze_card = Path(tmp) / "card_core_perp.md"
        missing_coinalyze_card.write_text(
            "\n".join([
                "# TESTPERP Event Research Card",
                "",
                "## Opportunity Lane",
                "- Opportunity type: CONFIRMED_LONG_RESEARCH",
                "- Why now: official/structured source plus fresh market confirmation",
                "",
                "## Derivatives / Crowding",
                "- Research-only. Not a trade signal.",
                "- Provider: coinalyze",
                "- Crowding class: high",
                "",
                "## Artifact Lineage",
                "- Core opportunity ID: core-perp",
            ]),
            encoding="utf-8",
        )
        coinalyze_card_conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
            [coinalyze_candidate],
            core_rows=[{**coinalyze_candidate, "row_type": "event_core_opportunity"}],
            research_card_paths=(missing_coinalyze_card,),
        )
    assert coinalyze_card_conflicts["integrated_coinalyze_crowding_card_missing"] == 1

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        manifest = tmp_path / "event_integrated_radar_input_manifest.json"
        manifest.write_text(
            json.dumps({
                "sidecars": [
                    {
                        "sidecar_name": "coinalyze",
                        "mode": "loaded_external_coinalyze",
                        "coinalyze_artifact_namespace": "external_coinalyze",
                        "coinalyze_artifact_namespace_status": "stale_deprecated",
                        "coinalyze_derivatives_state_rows_loaded": 2,
                        "coinalyze_crowding_candidates_loaded": 2,
                        "coinalyze_fade_review_candidates_loaded": 1,
                        "coinalyze_freshness_status": "stale",
                        "warnings": [],
                    }
                ]
            }),
            encoding="utf-8",
        )
        manifest_conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
            [
                {
                    "row_type": "event_integrated_radar_candidate",
                    "candidate_id": "iar:no-coinalyze",
                    "core_opportunity_id": "agg:no-coinalyze",
                    "symbol": "TEST",
                    "coin_id": "test",
                    "opportunity_type": "EARLY_LONG_RESEARCH",
                    "market_state_snapshot": {"market_state": "no_reaction"},
                    "source_strength": "official_structured",
                    "market_state_class": "no_reaction",
                }
            ],
            core_rows=[],
            manifest_path=manifest,
        )
    assert manifest_conflicts["integrated_coinalyze_loaded_no_rows_attached"] == 1
    assert manifest_conflicts["integrated_coinalyze_stale_loaded_without_warning"] == 1
    assert manifest_conflicts["integrated_coinalyze_loaded_from_stale_namespace"] == 1

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        manifest = tmp_path / "event_integrated_radar_input_manifest.json"
        manifest.write_text(
            json.dumps({
                "sidecars": [
                    {
                        "sidecar_name": "coinalyze",
                        "mode": "skipped_missing_artifact",
                        "coinalyze_artifact_namespace": "missing_coinalyze",
                        "coinalyze_derivatives_state_rows_loaded": 0,
                        "coinalyze_crowding_candidates_loaded": 0,
                        "coinalyze_fade_review_candidates_loaded": 0,
                        "warnings": ["coinalyze_artifacts_missing_or_empty"],
                    }
                ]
            }),
            encoding="utf-8",
        )
        skip_conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
            [candidate],
            core_rows=[{**candidate, "row_type": "event_core_opportunity"}],
            manifest_path=manifest,
        )
    assert skip_conflicts["integrated_coinalyze_missing_skip_reason"] == 1


def test_integrated_doctor_catches_delivery_and_outcome_conflicts():
    import json

    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    candidate = {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "iar:test",
        "core_opportunity_id": "agg:test",
        "symbol": "TEST",
        "coin_id": "test",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "market_state_snapshot": {"market_state": "no_reaction"},
        "source_strength": "official_structured",
        "market_state_class": "no_reaction",
    }
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        preview = tmp_path / "event_alpha_notification_preview.md"
        preview.write_text("Alertable decisions: 0 · Alerts: 1\nNo research-only disclaimer", encoding="utf-8")
        deliveries = tmp_path / "event_integrated_radar_notification_deliveries.jsonl"
        deliveries.write_text(
            "\n".join([
                json.dumps({
                    "row_type": "event_integrated_radar_notification_delivery",
                    "lane": "early_long_research",
                    "lane_title": "Early Long Research",
                    "message_text": "Card: /Users/test/card.md",
                    "sent": True,
                    "no_send_rehearsal": True,
                    "skipped_item_count": 1,
                    "card_paths": ["/Users/test/card.md"],
                    "normal_rsi_signal_written": True,
                }),
                json.dumps({
                    "row_type": "event_integrated_radar_notification_delivery",
                    "lane": "early_long_research",
                    "lane_title": "Early Long Research",
                    "message_text": "Research-only. Not a trade signal. Card: none",
                    "sent": False,
                    "no_send_rehearsal": True,
                    "skipped_item_count": 0,
                    "card_paths": ["event_fade_cache/test/research_cards/card_core_test.md"],
                }),
            ]) + "\n",
            encoding="utf-8",
        )
        outcomes = tmp_path / "event_integrated_radar_outcomes.jsonl"
        outcomes.write_text(
            json.dumps({
                "row_type": "event_integrated_radar_outcome",
                "candidate_id": "iar:test",
                "symbol": "",
                "coin_id": "",
                "opportunity_type": "DIAGNOSTIC",
                "primary_horizon_return": 10.0,
                "price_at_observation": None,
                "include_in_performance": True,
                "triggered_fade_created": True,
                "outcome_status": "missing_data",
            }) + "\n",
            encoding="utf-8",
        )
        (tmp_path / "event_integrated_radar_calibration_priors.json").write_text(
            json.dumps({
                "auto_apply": False,
                "recommendation_only": True,
                "eligible_for_auto_apply": False,
                "opportunity_type_priors": {
                    "DIAGNOSTIC": {"sample_size": 1, "auto_apply": True},
                    "EARLY_LONG_RESEARCH": {"sample_size": 1, "min_sample_size": 25},
                },
            }),
            encoding="utf-8",
        )
        manifest = tmp_path / "event_integrated_radar_input_manifest.json"
        manifest.write_text(json.dumps({"sidecars": []}), encoding="utf-8")
        daily = tmp_path / "event_alpha_daily_brief.md"
        daily.write_text("Input manifest: not available\n", encoding="utf-8")
        conflicts = event_alpha_artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
            [candidate],
            core_rows=[{**candidate, "row_type": "event_core_opportunity"}],
            daily_brief_path=daily,
            manifest_path=manifest,
            delivery_path=deliveries,
            outcome_path=outcomes,
            preview_path=preview,
        )
    assert conflicts["integrated_api_preview_alerts_wording"] == 1
    assert conflicts["integrated_delivery_missing_disclaimer"] == 1
    assert conflicts["integrated_delivery_sent_in_no_send"] == 1
    assert conflicts["integrated_delivery_side_effect_flag"] == 1
    assert conflicts["integrated_delivery_missing_skip_reasons"] == 1
    assert conflicts["integrated_delivery_card_path_absolute"] == 1
    assert conflicts["integrated_delivery_card_path_not_rendered"] == 1
    assert conflicts["operator_structured_path_absolute"] >= 1
    assert conflicts["integrated_manifest_daily_brief_unavailable"] == 1
    assert conflicts["integrated_outcome_side_effect_flag"] == 1
    assert conflicts["integrated_outcome_schema_missing"] >= 1
    assert conflicts["integrated_outcome_missing_identity"] == 1
    assert conflicts["integrated_outcome_returns_without_price"] == 1
    assert conflicts["integrated_outcome_diagnostic_in_performance"] == 1
    assert conflicts["integrated_calibration_diagnostic_in_main_priors"] == 1
    assert conflicts["integrated_calibration_prior_safety_missing"] >= 1
    assert conflicts["integrated_outcome_return_double_scaled"] == 1
    assert conflicts["integrated_outcome_missing_data_unlabeled"] == 1


def test_integrated_delivery_preview_check_allows_zero_candidate_legacy_burn_in():
    from crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_parts.outcome_checks import (
        _integrated_delivery_conflicts,
    )

    rows = [
        {
            "row_type": "event_integrated_radar_notification_delivery",
            "lane": "early_long_research",
            "lane_title": "Early Long Research",
            "message_text": "Research-only. Not a trade signal.",
            "sent": False,
            "no_send_rehearsal": True,
            "rendered_item_count": 0,
            "eligible_item_count": 0,
            "skipped_item_count": 0,
        },
        {
            "row_type": "event_integrated_radar_notification_delivery",
            "lane": "source_provider_health",
            "lane_title": "Source / Provider Health",
            "message_text": "Research-only. Not a trade signal.",
            "status": "would_send_but_guard_disabled",
            "would_send": True,
            "sent": False,
            "no_send_rehearsal": True,
            "rendered_item_count": 0,
            "eligible_item_count": 0,
            "skipped_item_count": 0,
        },
    ]
    conflicts = _integrated_delivery_conflicts(rows, preview_path=None)
    assert conflicts["integrated_preview_lane_mismatch"] == 0


def test_integrated_delivery_preview_check_blocks_rendered_rows_without_preview():
    from crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_parts.outcome_checks import (
        _integrated_delivery_conflicts,
    )

    rows = [
        {
            "row_type": "event_integrated_radar_notification_delivery",
            "lane": "early_long_research",
            "lane_title": "Early Long Research",
            "message_text": "Research-only. Not a trade signal.",
            "sent": False,
            "no_send_rehearsal": True,
            "rendered_item_count": 1,
            "eligible_item_count": 1,
            "skipped_item_count": 0,
        }
    ]
    conflicts = _integrated_delivery_conflicts(rows, preview_path=Path("missing_integrated_preview.md"))
    assert conflicts["integrated_preview_lane_mismatch"] == 1


def test_integrated_doctor_requires_thesis_interpretation_for_fade_and_risk_outcomes():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    candidate = {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "iar:fade",
        "core_opportunity_id": "core-fade",
        "symbol": "TESTFADE",
        "coin_id": "testfade",
        "opportunity_type": "FADE_SHORT_REVIEW",
        "market_state_snapshot": {"market_state": "post_event_fade_setup"},
        "market_state_class": "post_event_fade_setup",
    }
    missing_thesis = {
        "row_type": "event_integrated_radar_outcome",
        "candidate_id": "iar:fade",
        "symbol": "TESTFADE",
        "coin_id": "testfade",
        "opportunity_type": "FADE_SHORT_REVIEW",
        "outcome_label": "fade_review_good",
        "outcome_status": "filled",
        "primary_horizon_return": -0.12,
        "thesis_primary_move": None,
        "price_at_observation": 1.0,
        "include_in_performance": True,
        "no_trade_created": True,
        "no_paper_trade_created": True,
        "outcome_horizons": ["24h"],
        "return_by_horizon": {"24h": -0.12},
        "relative_return_vs_btc_by_horizon": {"24h": -0.14},
        "relative_return_vs_eth_by_horizon": {"24h": -0.13},
        "max_favorable_excursion_by_window": {"24h": -0.02},
        "max_adverse_excursion_by_window": {"24h": -0.12},
        "benchmark_btc_price_at_observation": 65000.0,
    }

    conflicts = event_alpha_artifact_doctor._integrated_outcome_conflicts(  # noqa: SLF001
        [candidate],
        [missing_thesis],
    )

    assert conflicts["integrated_outcome_thesis_move_missing"] == 1
    assert conflicts["integrated_outcome_schema_missing"] >= 1
