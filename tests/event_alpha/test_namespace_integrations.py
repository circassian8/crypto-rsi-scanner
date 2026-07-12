"""Cross-namespace Coinalyze, performance, stale handling, inventory, and doctor-policy regressions."""

from __future__ import annotations

from pathlib import Path

from crypto_rsi_scanner.event_alpha.namespace import lifecycle

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_integrated_calendar_normalization_is_single_pass_exact_and_scope_neutral():
    import json
    from collections import Counter
    from tempfile import TemporaryDirectory

    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
    import crypto_rsi_scanner.event_alpha.radar.integrated.pipeline_parts.cycle as event_integrated_cycle
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1

    original_fixture_path = event_integrated_cycle.config.EVENT_ALPHA_UNIFIED_CALENDAR_FIXTURE_PATH
    original_normalize = (
        event_integrated_cycle.event_unified_calendar.normalize_unified_calendar_rows_with_telemetry
    )
    original_legacy_fixture_loader = (
        event_integrated_cycle.event_unified_calendar.load_unified_calendar_fixture
    )
    normalization_calls = 0

    def counted_normalize(*args, **kwargs):
        nonlocal normalization_calls
        normalization_calls += 1
        return original_normalize(*args, **kwargs)

    def reject_legacy_fixture_loader(*args, **kwargs):
        raise AssertionError("integrated cycle pre-normalized the calendar fixture")

    event_integrated_cycle.event_unified_calendar.normalize_unified_calendar_rows_with_telemetry = (
        counted_normalize
    )
    event_integrated_cycle.event_unified_calendar.load_unified_calendar_fixture = (
        reject_legacy_fixture_loader
    )
    try:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            baseline_context = event_alpha_artifacts.context_from_profile(
                "fixture",
                run_mode="fixture",
                base_dir=base,
                artifact_namespace="calendar_scope_baseline",
            )
            event_integrated_cycle.config.EVENT_ALPHA_UNIFIED_CALENDAR_FIXTURE_PATH = (
                base / "missing-unified-calendar-fixture.json"
            )
            baseline = event_integrated_radar.run_integrated_radar_cycle(
                context=baseline_context,
                fixture=True,
                observed_at="2026-06-15T16:00:00Z",
            )
            assert normalization_calls == 1

            actual_context = event_alpha_artifacts.context_from_profile(
                "fixture",
                run_mode="fixture",
                base_dir=base,
                artifact_namespace="calendar_scope_actual",
            )
            event_integrated_cycle.config.EVENT_ALPHA_UNIFIED_CALENDAR_FIXTURE_PATH = (
                original_fixture_path
            )
            result = event_integrated_radar.run_integrated_radar_cycle(
                context=actual_context,
                fixture=True,
                observed_at="2026-06-15T16:00:00Z",
            )
            assert normalization_calls == 2

            telemetry = dict(result.unified_calendar_normalization or {})
            expected_fields = {
                "contract_version",
                "dedupe_policy",
                "input_rows",
                "accepted_rows",
                "output_rows",
                "duplicate_overwrite_rows",
                "non_mapping_rows",
                "rejected_rows",
                "rejected_reason_counts",
            }
            assert set(telemetry) == expected_fields
            assert telemetry["contract_version"] == 1
            assert telemetry["dedupe_policy"] == "last_valid_row_wins"
            assert telemetry["input_rows"] == (
                result.scheduled_catalysts
                + len(
                    event_integrated_cycle.event_unified_calendar.load_unified_calendar_fixture_raw_rows(
                        original_fixture_path
                    )
                )
            )
            assert telemetry["input_rows"] == (
                telemetry["accepted_rows"]
                + telemetry["non_mapping_rows"]
                + telemetry["rejected_rows"]
            )
            assert telemetry["accepted_rows"] == (
                telemetry["output_rows"] + telemetry["duplicate_overwrite_rows"]
            )
            assert telemetry["rejected_rows"] == sum(
                telemetry["rejected_reason_counts"].values()
            )

            calendar_lines = [
                line
                for line in result.unified_calendar_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            calendar_rows = [json.loads(line) for line in calendar_lines]
            assert telemetry["output_rows"] == result.unified_calendar_rows == len(calendar_lines)
            assert all(
                row[counter] == 0
                for row in calendar_rows
                for counter in (
                    "strict_alerts_created",
                    "telegram_sends",
                    "trades_created",
                    "paper_trades_created",
                    "normal_rsi_signal_rows_written",
                    "triggered_fade_created",
                )
            )

            run_row = json.loads(
                actual_context.run_ledger_path.read_text(encoding="utf-8").splitlines()[-1]
            )
            assert run_row["unified_calendar_normalization"] == telemetry
            assert run_row["unified_calendar_rows"] == telemetry["output_rows"]
            assert schema_v1.validate_row_against_schema(run_row, "run_ledger_v1") == []
            run_report = event_integrated_cycle.event_alpha_run_ledger.format_run_ledger_report(
                event_integrated_cycle.event_alpha_run_ledger.EventAlphaRunLedgerReadResult(
                    path=actual_context.run_ledger_path,
                    rows_read=1,
                    rows=[run_row],
                )
            )
            assert "calendar_normalization: input=12 accepted=10 output=10" in run_report
            assert "reasons=unsupported_event_kind=2" in run_report
            assert result.strict_alerts == run_row["strict_alerts"] == 0
            assert result.send_attempted is False
            assert result.send_items_delivered == 0
            assert run_row["sent"] is False

            baseline_manifest = json.loads(
                baseline.input_manifest_path.read_text(encoding="utf-8")
            )
            actual_manifest = json.loads(result.input_manifest_path.read_text(encoding="utf-8"))
            assert result.raw_events == baseline.raw_events == sum(actual_manifest["row_counts"].values())
            assert result.scheduled_catalysts == baseline.scheduled_catalysts == actual_manifest[
                "row_counts"
            ]["scheduled_catalyst"]
            assert baseline_manifest["row_counts"] == actual_manifest["row_counts"]
            assert result.candidates == baseline.candidates
            assert result.integrated_candidates == baseline.integrated_candidates

            def lane_counts(path):
                return Counter(
                    json.loads(line)["opportunity_type"]
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )

            assert lane_counts(result.integrated_candidates_path) == lane_counts(
                baseline.integrated_candidates_path
            )
    finally:
        event_integrated_cycle.config.EVENT_ALPHA_UNIFIED_CALENDAR_FIXTURE_PATH = (
            original_fixture_path
        )
        event_integrated_cycle.event_unified_calendar.normalize_unified_calendar_rows_with_telemetry = (
            original_normalize
        )
        event_integrated_cycle.event_unified_calendar.load_unified_calendar_fixture = (
            original_legacy_fixture_loader
        )


def test_integrated_radar_loads_external_coinalyze_namespace():
    import json
    from datetime import datetime, timezone

    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
    import crypto_rsi_scanner.event_alpha.namespace.status as event_alpha_namespace_status
    import crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight as event_coinalyze_preflight
    import crypto_rsi_scanner.event_alpha.radar.derivatives_crowding as event_derivatives_crowding
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar
    import crypto_rsi_scanner.event_alpha.providers.live_provider_readiness as event_live_provider_readiness

    payload = {
        "derivatives": [
            {
                "symbol": "TESTFADE",
                "coin_id": "test-fade",
                "open_interest_delta_24h": 0.58,
                "funding_rate": 0.0012,
                "funding_zscore": 3.2,
                "liquidation_long_usd": 2_800_000,
                "liquidation_short_usd": 500_000,
                "perp_volume": 90_000_000,
                "spot_volume": 30_000_000,
                "freshness_status": "fresh",
            },
            {
                "symbol": "TESTPERP",
                "coin_id": "test-perp",
                "market": "TESTPERPUSDT_PERP.A",
                "open_interest_delta_24h": 0.44,
                "funding_rate": 0.0008,
                "funding_zscore": 2.6,
                "liquidation_long_usd": 800_000,
                "liquidation_short_usd": 110_000,
                "perp_volume": 42_000_000,
                "spot_volume": 10_000_000,
                "freshness_status": "fresh",
            },
        ],
        "candidates": [
            {
                "symbol": "TESTFADE",
                "coin_id": "test-fade",
                "event_name": "TESTFADE listing blowoff",
                "source_class": "official_exchange",
                "source_pack": "listing_liquidity_pack",
                "impact_path_type": "listing_liquidity_event",
                "evidence_quality_score": 92,
                "accepted_evidence_count": 1,
                "market_snapshot": {
                    "return_unit": "fraction",
                    "return_4h": 0.21,
                    "return_24h": 0.42,
                    "volume_zscore_24h": 4.8,
                    "liquidity_usd": 3_500_000,
                    "spread_bps": 42,
                    "event_age_hours": 3,
                },
            },
            {
                "symbol": "TESTPERP",
                "coin_id": "test-perp",
                "event_name": "TESTPERP perp breakout",
                "source_class": "official_exchange",
                "source_pack": "perp_listing_squeeze_pack",
                "impact_path_type": "listing_liquidity_event",
                "evidence_quality_score": 92,
                "accepted_evidence_count": 1,
                "market_snapshot": {
                    "return_unit": "fraction",
                    "return_4h": 0.11,
                    "return_24h": 0.18,
                    "volume_zscore_24h": 3.4,
                    "liquidity_usd": 18_000_000,
                    "spread_bps": 18,
                    "event_age_hours": -1,
                },
            },
        ],
    }
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        coinalyze_dir = base / "external_coinalyze"
        fixture_path = base / "coinalyze_payload.json"
        fixture_path.write_text(json.dumps(payload), encoding="utf-8")
        event_derivatives_crowding.run_derivatives_crowding_scan(
            namespace_dir=coinalyze_dir,
            derivatives_path=fixture_path,
            profile="fixture",
            artifact_namespace="external_coinalyze",
            run_mode="fixture",
            run_id="coinalyze-run",
            observed_at=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
        )
        (coinalyze_dir / event_coinalyze_preflight.REHEARSAL_JSON).write_text(
            json.dumps({
                "status": "live_rehearsal_success",
                "provider_health_status": "observed_healthy",
                "snapshots_written": 2,
                "crowding_candidates_written": 2,
                "fade_review_candidates_written": 1,
            }),
            encoding="utf-8",
        )
        context = event_alpha_artifacts.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=base,
            artifact_namespace="integrated_test",
        )
        result = event_integrated_radar.run_integrated_radar_cycle(
            context=context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
            coinalyze_namespace="external_coinalyze",
        )
        rows = [
            json.loads(line)
            for line in result.integrated_candidates_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        by_symbol = {row["symbol"]: row for row in rows}
        assert by_symbol["TESTPERP"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
        assert by_symbol["TESTPERP"]["coinalyze_derivatives_attached"] is True
        assert by_symbol["TESTPERP"]["coinalyze_artifact_namespace"] == "external_coinalyze"
        assert "confirmed_long_derivatives_crowding_warning" in by_symbol["TESTPERP"]["warnings"]
        assert by_symbol["TESTFADE"]["opportunity_type"] == "FADE_SHORT_REVIEW"
        assert by_symbol["TESTFADE"]["coinalyze_derivatives_attached"] is True
        assert by_symbol["TESTFADE"]["crowding_class"] == "extreme"
        assert "open_interest_delta_24h_high" in by_symbol["TESTFADE"]["crowding_exhaustion_evidence"]

        manifest = json.loads(result.input_manifest_path.read_text(encoding="utf-8"))
        assert manifest["coinalyze_artifact_namespace"] == "external_coinalyze"
        assert manifest["coinalyze_derivatives_state_rows_loaded"] == 2
        assert manifest["coinalyze_crowding_candidates_loaded"] == 2
        assert manifest["coinalyze_fade_review_candidates_loaded"] == 1
        assert manifest["coinalyze_provider_health_status"] == "observed_healthy"
        assert manifest["coinalyze_freshness_status"] == "fresh"
        assert manifest["coinalyze_skip_reason"] is None
        coverage = json.loads(result.source_coverage_json_path.read_text(encoding="utf-8"))
        assert coverage["generated_at"] == "2026-06-15T16:00:00+00:00"
        assert coverage["coinalyze_derivatives_state_rows_loaded"] == 2
        assert "cryptopanic_configured" in coverage
        assert "cryptopanic_selected_for_run" in coverage
        assert "cryptopanic_live_call_allowed" in coverage
        assert "cryptopanic_observed" in coverage
        assert "cryptopanic_not_used_reason" in coverage
        assert "cryptopanic_coverage_status" in coverage
        assert coverage["candidates_blocked_by_source_coverage"] > 0
        assert coverage["candidate_families_blocked_by_source_coverage"] > 0
        run_row = json.loads(context.run_ledger_path.read_text(encoding="utf-8").splitlines()[-1])
        assert run_row["cryptopanic_configured"] is coverage["cryptopanic_configured"]
        if coverage["cryptopanic_configured"]:
            assert coverage["cryptopanic_selected_for_run"] is False
            assert coverage["cryptopanic_live_call_allowed"] is False
            assert coverage["cryptopanic_observed"] is False
            assert coverage["cryptopanic_not_used_reason"] == "profile_disabled"
            assert coverage["cryptopanic_coverage_status"] == "configured_profile_disabled"
        daily = result.daily_brief_path.read_text(encoding="utf-8")
        assert "### Derivatives/OI/funding status" in daily
        assert "namespace=external_coinalyze" in daily
        assert "event_derivatives_state.jsonl" in daily
        cards = "\n".join(path.read_text(encoding="utf-8") for path in result.research_card_paths if path.name != "index.md")
        assert "Coinalyze source: namespace=external_coinalyze" in cards
        assert "/Users/" not in cards

        auto_context = event_alpha_artifacts.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=base,
            artifact_namespace="integrated_auto",
        )
        event_integrated_radar.run_integrated_radar_cycle(
            context=auto_context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
        )
        (auto_context.namespace_dir / event_live_provider_readiness.READINESS_JSON).write_text(
            json.dumps({
                "providers": [
                    {
                        "provider_name": "coinalyze",
                        "latest_request_ledger_path": "event_fade_cache/external_coinalyze/event_coinalyze_request_ledger.jsonl",
                    }
                ]
            }),
            encoding="utf-8",
        )
        auto_result = event_integrated_radar.run_integrated_radar_cycle(
            context=auto_context,
            input_mode=event_integrated_radar.INPUT_MODE_LOAD_EXISTING,
            observed_at="2026-06-15T16:00:00Z",
        )
        auto_manifest = json.loads(auto_result.input_manifest_path.read_text(encoding="utf-8"))
        assert auto_manifest["coinalyze_artifact_namespace"] == "external_coinalyze"
        assert auto_manifest["coinalyze_derivatives_state_rows_loaded"] == 2
        assert auto_manifest["sidecars"][-1]["coinalyze_artifact_selection_mode"] == "readiness_auto"

        event_alpha_namespace_status.mark_namespace_stale(
            coinalyze_dir,
            namespace="external_coinalyze",
            reason="test stale namespace",
            superseded_by="new_coinalyze",
            now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
        )
        stale_context = event_alpha_artifacts.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=base,
            artifact_namespace="integrated_stale",
        )
        stale_result = event_integrated_radar.run_integrated_radar_cycle(
            context=stale_context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
            coinalyze_namespace="external_coinalyze",
        )
        stale_manifest = json.loads(stale_result.input_manifest_path.read_text(encoding="utf-8"))
        assert stale_manifest["coinalyze_derivatives_state_rows_loaded"] == 0
        assert stale_manifest["coinalyze_skip_reason"] == "coinalyze_namespace_stale_deprecated"
        assert "coinalyze_namespace_stale_deprecated" in stale_manifest["warnings"]

        missing_context = event_alpha_artifacts.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=base,
            artifact_namespace="integrated_missing",
        )
        missing_result = event_integrated_radar.run_integrated_radar_cycle(
            context=missing_context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
            coinalyze_namespace="missing_coinalyze",
        )
        missing_manifest = json.loads(missing_result.input_manifest_path.read_text(encoding="utf-8"))
        assert missing_manifest["coinalyze_artifact_namespace"] == "missing_coinalyze"
        assert missing_manifest["coinalyze_skip_reason"] == "coinalyze_artifacts_missing_or_empty"


def test_integrated_radar_performance_dashboard_cross_namespace_recommendations():
    import json

    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar
    import crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes as event_integrated_radar_outcomes

    def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    def candidate(
        candidate_id: str,
        symbol: str,
        lane: str,
        provider: str,
        source_pack: str,
        *,
        source_origin: str = "official_exchange",
        market_state_class: str = "confirmed_breakout",
        crowding_class: str = "none",
    ) -> dict[str, object]:
        return {
            "row_type": "event_integrated_radar_candidate",
            "candidate_id": candidate_id,
            "core_opportunity_id": f"core-{candidate_id}",
            "symbol": symbol,
            "coin_id": symbol.casefold(),
            "opportunity_type": lane,
            "provider": provider,
            "source_origin": source_origin,
            "source_pack": source_pack,
            "market_state_class": market_state_class,
            "crowding_class": crowding_class,
            "source_strength": "official_structured" if source_origin == "official_exchange" else "context_only",
            "observed_at": "2026-06-15T16:00:00+00:00",
        }

    def outcome(candidate_row: dict[str, object], label: str, *, status: str = "filled") -> dict[str, object]:
        lane = str(candidate_row["opportunity_type"])
        row = {
            "row_type": "event_integrated_radar_outcome",
            "candidate_id": candidate_row["candidate_id"],
            "core_opportunity_id": candidate_row["core_opportunity_id"],
            "symbol": candidate_row["symbol"],
            "coin_id": candidate_row["coin_id"],
            "opportunity_type": lane,
            "outcome_status": status,
            "outcome_label": label,
            "return_by_horizon": {horizon: 0.04 for horizon in event_integrated_radar_outcomes.HORIZONS},
            "horizons": {horizon: 0.04 for horizon in event_integrated_radar_outcomes.HORIZONS},
            "time_to_peak_hours": 24.0,
            "time_to_trough_hours": 24.0,
        }
        if status == "missing_data":
            row["missing_data_reason"] = "no_cached_price_fixture"
            row["return_by_horizon"] = {}
            row["horizons"] = {}
        return row

    def core(candidate_row: dict[str, object]) -> dict[str, object]:
        row = dict(candidate_row)
        row["integrated_candidate_id"] = row.pop("candidate_id")
        return row

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        ns1 = base / "ns_one"
        ns2 = base / "ns_two"
        out = base / "dashboard"
        bybit = candidate(
            "bybit-early",
            "TESTLIST",
            "EARLY_LONG_RESEARCH",
            "bybit",
            "official_exchange_listing_pack",
            market_state_class="no_reaction",
        )
        coinalyze = candidate(
            "coinalyze-fade",
            "TESTFADE",
            "FADE_SHORT_REVIEW",
            "coinalyze",
            "derivatives_crowding_pack",
            source_origin="derivatives",
            market_state_class="post_event_fade_setup",
            crowding_class="extreme",
        )
        pending = candidate(
            "cryptopanic-pending",
            "TESTPEND",
            "UNCONFIRMED_RESEARCH",
            "cryptopanic",
            "cryptopanic_tagged_news_pack",
            source_origin="source_news",
        )
        missing = candidate(
            "cryptopanic-missing",
            "TESTMISS",
            "UNCONFIRMED_RESEARCH",
            "cryptopanic",
            "cryptopanic_tagged_news_pack",
            source_origin="source_news",
        )
        cryptopanic = candidate(
            "cryptopanic-noise",
            "TESTRUMOR",
            "UNCONFIRMED_RESEARCH",
            "cryptopanic",
            "cryptopanic_tagged_news_pack",
            source_origin="source_news",
        )
        diagnostic = candidate(
            "sector-diagnostic",
            "SECTOR",
            "DIAGNOSTIC",
            "fixture",
            "diagnostic_pack",
            source_origin="diagnostic",
        )
        write_jsonl(ns1 / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME, [bybit, coinalyze, pending, missing])
        write_jsonl(ns1 / "event_core_opportunities.jsonl", [
            core(bybit), core(coinalyze), core(pending), core(missing),
        ])
        write_jsonl(
            ns1 / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME,
            [
                outcome(bybit, "early_good"),
                outcome(coinalyze, "fade_review_good"),
                outcome(missing, "missing_data", status="missing_data"),
            ],
        )
        write_jsonl(ns2 / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME, [cryptopanic, diagnostic])
        write_jsonl(ns2 / "event_core_opportunities.jsonl", [core(cryptopanic), core(diagnostic)])
        write_jsonl(
            ns2 / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME,
            [outcome(cryptopanic, "remained_noise"), outcome(diagnostic, "diagnostic_only")],
        )

        payload = event_integrated_radar_outcomes.write_radar_performance_dashboard(
            (ns1, ns2),
            output_namespace_dir=out,
            generated_at="2026-06-20T00:00:00+00:00",
        )

        assert (out / event_integrated_radar.RADAR_PERFORMANCE_DASHBOARD_FILENAME).exists()
        assert (out / event_integrated_radar.RADAR_PROVIDER_PERFORMANCE_FILENAME).exists()
        assert payload["thresholds_changed"] is False
        assert payload["auto_apply"] is False
        assert payload["rows_evaluated"] == 0
        assert payload["diagnostic_rows_excluded"] == 2
        assert payload["calibration_ineligible_rows_excluded"] == 9
        assert payload["maturation_counts"]["matured"] == 3
        assert payload["maturation_counts"]["pending"] == 5
        assert payload["maturation_counts"]["missing_price_data"] == 1
        assert payload["performance_views"]["early_long_conversion_rate"]["rate"] is None
        assert payload["performance_views"]["fade_review_exhaustion_rate"]["rate"] is None
        assert payload["performance_views"]["unconfirmed_later_confirmation_noise_rate"]["noise_rate"] is None
        assert {"bybit", "coinalyze", "cryptopanic"} <= set(payload["provider_performance"])
        assert payload["provider_performance"]["coinalyze"]["validated_count"] == 0
        assert payload["provider_performance"]["cryptopanic"]["invalidated_noise_count"] == 0
        assert payload["provider_prior_suggestions"]["bybit"]["auto_apply"] is False
        assert payload["provider_prior_suggestions"]["bybit"]["min_sample_warning"] is True
        assert payload["source_pack_prior_suggestions"]["official_exchange_listing_pack"]["auto_apply"] is False
        assert payload["lane_threshold_suggestions"]["FADE_SHORT_REVIEW"]["auto_apply"] is False
        dashboard = (out / event_integrated_radar.RADAR_PERFORMANCE_DASHBOARD_FILENAME).read_text(encoding="utf-8")
        assert "Radar Performance Dashboard" in dashboard
        assert "Recommendations only" in dashboard
        assert "trade" not in dashboard.casefold()
        assert "paper" not in dashboard.casefold()
        assert "pnl" not in dashboard.casefold()
        assert "p&l" not in dashboard.casefold()
        assert event_alpha_artifact_doctor._integrated_performance_dashboard_conflicts(out) == {  # noqa: SLF001
            "integrated_performance_diagnostic_in_main_aggregate": 0,
            "integrated_performance_auto_apply_enabled": 0,
            "integrated_performance_low_sample_missing_warning": 0,
            "integrated_performance_trade_pnl_wording": 0,
        }

        bad_payload = json.loads(json.dumps(payload))
        bad_payload["provider_prior_suggestions"]["bybit"]["auto_apply"] = True
        (out / event_integrated_radar.RADAR_PROVIDER_PERFORMANCE_FILENAME).write_text(
            json.dumps(bad_payload, sort_keys=True),
            encoding="utf-8",
        )
        assert event_alpha_artifact_doctor._integrated_performance_dashboard_conflicts(out)[  # noqa: SLF001
            "integrated_performance_auto_apply_enabled"
        ] > 0

        bad_payload = json.loads(json.dumps(payload))
        bad_payload["provider_prior_suggestions"]["bybit"].pop("min_sample_warning")
        (out / event_integrated_radar.RADAR_PROVIDER_PERFORMANCE_FILENAME).write_text(
            json.dumps(bad_payload, sort_keys=True),
            encoding="utf-8",
        )
        assert event_alpha_artifact_doctor._integrated_performance_dashboard_conflicts(out)[  # noqa: SLF001
            "integrated_performance_low_sample_missing_warning"
        ] > 0

        bad_payload = json.loads(json.dumps(payload))
        bad_payload["lane_summaries"]["DIAGNOSTIC"] = {"rows": 1}
        (out / event_integrated_radar.RADAR_PROVIDER_PERFORMANCE_FILENAME).write_text(
            json.dumps(bad_payload, sort_keys=True),
            encoding="utf-8",
        )
        assert event_alpha_artifact_doctor._integrated_performance_dashboard_conflicts(out)[  # noqa: SLF001
            "integrated_performance_diagnostic_in_main_aggregate"
        ] == 1

        (out / event_integrated_radar.RADAR_PROVIDER_PERFORMANCE_FILENAME).write_text(
            json.dumps(payload, sort_keys=True),
            encoding="utf-8",
        )
        (out / event_integrated_radar.RADAR_PERFORMANCE_DASHBOARD_FILENAME).write_text(
            dashboard + "\nPnL trade wording should block.\n",
            encoding="utf-8",
        )
        assert event_alpha_artifact_doctor._integrated_performance_dashboard_conflicts(out)[  # noqa: SLF001
            "integrated_performance_trade_pnl_wording"
        ] == 1


def test_integrated_radar_performance_joins_real_core_shape_without_double_counting():
    import json

    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar
    import crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes as event_integrated_radar_outcomes

    with TemporaryDirectory() as tmp:
        namespace = Path(tmp) / "real_core_shape"
        namespace.mkdir()
        candidates = []
        cores = []
        outcomes = []
        for index in range(11):
            candidate_id = f"iar:candidate-{index}"
            core_id = f"agg:core-{index}"
            lane = "DIAGNOSTIC" if index >= 9 else "EARLY_LONG_RESEARCH"
            candidate = {
                "row_type": "event_integrated_radar_candidate",
                "candidate_id": candidate_id,
                "core_opportunity_id": core_id,
                "symbol": f"TEST{index}",
                "coin_id": f"test-{index}",
                "opportunity_type": lane,
                "provider": "fixture",
                "source_pack": "fixture_pack",
                "observed_at": "2026-06-15T16:00:00+00:00",
            }
            candidates.append(candidate)
            if lane != "DIAGNOSTIC":
                core = dict(candidate)
                core["row_type"] = "event_core_opportunity"
                core["integrated_candidate_id"] = core.pop("candidate_id")
                cores.append(core)
            outcomes.append({
                **candidate,
                "row_type": "event_integrated_radar_outcome",
                "outcome_status": "filled",
                "outcome_label": "diagnostic_only" if lane == "DIAGNOSTIC" else "early_good",
                "return_by_horizon": {
                    horizon: 0.04 for horizon in event_integrated_radar_outcomes.HORIZONS
                },
                "horizons": {
                    horizon: 0.04 for horizon in event_integrated_radar_outcomes.HORIZONS
                },
            })

        for filename, rows in (
            (event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME, candidates),
            ("event_core_opportunities.jsonl", cores),
            (event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME, outcomes),
        ):
            (namespace / filename).write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )

        inputs = event_integrated_radar_outcomes._namespace_inputs(  # noqa: SLF001
            namespace,
            generated_at="2026-06-20T00:00:00+00:00",
            stale_after_days=14,
        )
        payload = event_integrated_radar_outcomes.build_radar_provider_performance(
            (namespace,),
            generated_at="2026-06-20T00:00:00+00:00",
        )

        assert len(inputs["rows"]) == 22
        assert len({row["candidate_id"] for row in inputs["rows"]}) == 11
        assert all(row["calibration_eligible"] is False for row in inputs["rows"])
        assert all(
            sum(row["core_opportunity_id"] == core["core_opportunity_id"] for row in inputs["rows"]) == 2
            for core in cores
        )
        assert payload["rows_evaluated"] == 0
        assert payload["diagnostic_rows_excluded"] == 4
        assert payload["calibration_ineligible_rows_excluded"] == 18
        assert payload["main_aggregate"]["rows"] == 0


def test_integrated_radar_performance_deduplicates_outcomes_and_joins_idless_fallback():
    import crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcomes as event_integrated_radar_outcomes

    idless = {
        "symbol": "IDLESS",
        "coin_id": "idless",
        "opportunity_type": "EARLY_LONG_RESEARCH",
        "observed_at": "2026-06-15T16:00:00+00:00",
    }
    identified = {
        "candidate_id": "candidate-duplicate-outcome",
        "symbol": "DUP",
        "coin_id": "duplicate",
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "observed_at": "2026-06-15T16:00:00+00:00",
    }
    rows = event_integrated_radar_outcomes._performance_observation_rows(  # noqa: SLF001
        Path("fixture"),
        candidates=[idless, identified],
        core_rows=[],
        outcome_rows=[
            {**idless, "outcome_status": "filled", "outcome_label": "early_good"},
            {**identified, "outcome_status": "filled", "outcome_label": "remained_noise"},
            {**identified, "outcome_status": "filled", "outcome_label": "later_confirmed"},
        ],
        delivery_rows=[],
        generated_at="2026-06-20T00:00:00+00:00",
        stale_after_days=14,
    )

    assert len(rows) == 5
    assert sum(row["symbol"] == "IDLESS" for row in rows) == 2
    assert sum(row["symbol"] == "DUP" for row in rows) == 3
    assert all(row["calibration_eligible"] is False for row in rows)
    assert all(row["validation_label"] == "inconclusive" for row in rows)


def test_integrated_performance_doctor_scopes_diagnostic_to_lane_and_route():
    import json

    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    valid = {
        "main_aggregate": {"rows": 4},
        "lane_summaries": {"EARLY_LONG_RESEARCH": {"rows": 4}},
        "dimension_summaries": {
            "confidence_band": {"diagnostic": {"rows": 1}, "actionable": {"rows": 3}},
            "opportunity_type": {"EARLY_LONG_RESEARCH": {"rows": 4}},
            "radar_route": {"actionable_watch": {"rows": 4}},
        },
        "performance_views": {},
        "provider_performance": {},
    }
    assert not event_alpha_artifact_doctor._performance_main_sections_contain_diagnostic(valid)  # noqa: SLF001

    diagnostic_lane = json.loads(json.dumps(valid))
    diagnostic_lane["lane_summaries"]["DIAGNOSTIC"] = {"rows": 1}
    assert event_alpha_artifact_doctor._performance_main_sections_contain_diagnostic(diagnostic_lane)  # noqa: SLF001

    diagnostic_route = json.loads(json.dumps(valid))
    diagnostic_route["dimension_summaries"]["radar_route"]["diagnostic"] = {"rows": 1}
    assert event_alpha_artifact_doctor._performance_main_sections_contain_diagnostic(diagnostic_route)  # noqa: SLF001


def test_event_alpha_coinalyze_stale_namespace_blocks_without_override():
    import contextlib
    import io
    from datetime import datetime, timezone
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.namespace.status as event_alpha_namespace_status
    import crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight as event_coinalyze_preflight

    original_base = config.EVENT_ALPHA_ARTIFACT_BASE_DIR
    original_namespace = config.EVENT_ALPHA_ARTIFACT_NAMESPACE
    original_override = os.environ.get("ALLOW_STALE_NAMESPACE_WRITE")
    try:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            config.EVENT_ALPHA_ARTIFACT_BASE_DIR = base
            config.EVENT_ALPHA_ARTIFACT_NAMESPACE = "notify_llm_deep"
            namespace_dir = base / "notify_llm_deep"
            event_alpha_namespace_status.mark_namespace_stale(
                namespace_dir,
                namespace="notify_llm_deep",
                reason="unit test stale namespace",
                superseded_by=event_coinalyze_preflight.DEFAULT_PREFLIGHT_NAMESPACE,
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
            )
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                scanner.event_alpha_coinalyze_preflight_report(
                    profile_name="notify_llm_deep",
                    artifact_namespace="notify_llm_deep",
                )
            output = buf.getvalue()
            assert "status=blocked_stale_namespace" in output
            assert "active_suggested_namespace=coinalyze_preflight" in output
            assert not (namespace_dir / event_coinalyze_preflight.PREFLIGHT_JSON).exists()
    finally:
        config.EVENT_ALPHA_ARTIFACT_BASE_DIR = original_base
        config.EVENT_ALPHA_ARTIFACT_NAMESPACE = original_namespace
        if original_override is None:
            os.environ.pop("ALLOW_STALE_NAMESPACE_WRITE", None)
        else:
            os.environ["ALLOW_STALE_NAMESPACE_WRITE"] = original_override


def test_event_alpha_namespace_lifecycle_inventory_and_archive_plan():
    from crypto_rsi_scanner.event_alpha.namespace import lifecycle
    import crypto_rsi_scanner.event_alpha.namespace.status as event_alpha_namespace_status

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        integrated = base / "integrated_radar_smoke"
        integrated.mkdir()
        for name in (
            "event_integrated_radar_candidates.jsonl",
            "event_core_opportunities.jsonl",
            "event_alpha_source_coverage.json",
        ):
            (integrated / name).write_text("{}\n", encoding="utf-8")
        stale = base / "notify_llm_deep"
        stale.mkdir()
        event_alpha_namespace_status.mark_namespace_stale(
            stale,
            namespace="notify_llm_deep",
            reason="unit stale namespace",
            superseded_by="integrated_radar_smoke",
        )

        report = lifecycle.write_namespace_lifecycle_report(base, out_dir=base)
        assert (base / lifecycle.REGISTRY_FILENAME).exists()
        assert (base / lifecycle.REPORT_FILENAME).exists()
        assert (integrated / event_alpha_namespace_status.NAMESPACE_STATUS_FILENAME).exists()
        assert (stale / event_alpha_namespace_status.NAMESPACE_STATUS_FILENAME).exists()
        rows = {row["namespace"]: row for row in report["namespaces"]}
        assert rows["integrated_radar_smoke"]["status"] == "active_integrated_smoke"
        assert rows["integrated_radar_smoke"]["missing_key_artifacts"] == []
        assert rows["integrated_radar_smoke"]["profile"] == "fixture"
        assert rows["integrated_radar_smoke"]["readiness_required"] is True
        assert rows["integrated_radar_smoke"]["readiness_present"] is True
        assert rows["notify_llm_deep"]["status"] == "stale_deprecated"
        assert rows["notify_llm_deep"]["safe_for_send_readiness"] is False
        marker = event_alpha_namespace_status.load_namespace_status(integrated)
        assert marker is not None
        assert marker.status == "active_integrated_smoke"
        assert marker.profile == "fixture"
        assert marker.current_doctor_status == "not_run"
        report_text = (base / lifecycle.REPORT_FILENAME).read_text(encoding="utf-8")
        assert "Event Alpha Namespace Lifecycle" in report_text
        assert "Active Doctor Status" in report_text
        assert "Research artifact inventory only" in report_text
        plan = lifecycle.archive_stale_namespaces_plan(base)
        assert plan["dry_run"] is True
        assert plan["archive_performed"] is False
        assert plan["stale_namespace_count"] == 1
        assert stale.exists()
        requested = lifecycle.archive_stale_namespaces_plan(base, dry_run=False)
        assert requested["dry_run"] is True
        assert requested["requested_dry_run"] is False
        assert requested["archive_performed"] is False
        assert stale.exists()


def test_event_alpha_namespace_lifecycle_doctor_policy_messages():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.namespace.status as event_alpha_namespace_status

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        unknown = base / "mystery_namespace"
        event_alpha_namespace_status.write_namespace_status(
            unknown,
            {
                "namespace": "mystery_namespace",
                "status": "unknown",
                "safe_for_send_readiness": False,
                "current_doctor_status": "not_run",
            },
        )
        unknown_result = event_alpha_artifact_doctor.diagnose_artifacts(
            source_coverage_report_path=unknown / "event_alpha_source_coverage.md",
            skip_api_checks=True,
        )
        assert unknown_result.status == "WARN"
        assert any("unknown_namespace_status=unknown" in warning for warning in unknown_result.warnings)

        unsafe = base / "unsafe_live"
        event_alpha_namespace_status.write_namespace_status(
            unsafe,
            {
                "namespace": "unsafe_live",
                "status": "active_live_rehearsal",
                "safe_for_send_readiness": True,
                "current_doctor_status": "BLOCKED",
            },
        )
        unsafe_result = event_alpha_artifact_doctor.diagnose_artifacts(
            source_coverage_report_path=unsafe / "event_alpha_source_coverage.md",
            skip_api_checks=True,
        )
        assert unsafe_result.status == "BLOCKED"
        assert any("current_doctor_status=BLOCKED" in blocker for blocker in unsafe_result.blockers)

        old_active = base / "old_active"
        event_alpha_namespace_status.write_namespace_status(
            old_active,
            {
                "namespace": "old_active",
                "status": "active_live_rehearsal",
                "safe_for_send_readiness": False,
                "current_doctor_status": "OK",
                "last_updated_at": "2000-01-01T00:00:00+00:00",
                "archive_after_days": 1,
            },
        )
        old_result = event_alpha_artifact_doctor.diagnose_artifacts(
            source_coverage_report_path=old_active / "event_alpha_source_coverage.md",
            skip_api_checks=True,
        )
        assert old_result.status == "WARN"
        assert any("active_namespace_older_than_retention=old_active" in warning for warning in old_result.warnings)
