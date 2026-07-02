"""Focused pytest checks for Event Alpha schema v1."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.doctor import schema_doctor


def test_schema_registry_contains_required_ids():
    assert "integrated_radar_candidate_v1" in schema_v1.SCHEMAS
    assert "namespace_status_v1" in schema_v1.SCHEMAS
    assert schema_doctor.check_registry_schema_dependency_errors() == ()


def test_artifact_module_import_shims_match_new_package_paths():
    from crypto_rsi_scanner import (
        event_alpha_artifacts as old_context,
        event_alpha_namespace_status as old_namespace_status,
        event_alpha_retention as old_retention,
        event_alpha_run_ledger as old_run_ledger,
        event_alpha_run_lock as old_locks,
        event_artifact_paths as old_paths,
    )
    from crypto_rsi_scanner.event_alpha.artifacts import (
        context as new_context,
        locks as new_locks,
        paths as new_paths,
        retention as new_retention,
        run_ledger as new_run_ledger,
    )
    from crypto_rsi_scanner.event_alpha.namespace import status as new_namespace_status

    assert old_context.context_from_profile is new_context.context_from_profile
    assert old_context.EventAlphaArtifactContext is new_context.EventAlphaArtifactContext
    assert old_paths.artifact_display_path is new_paths.artifact_display_path
    assert old_paths.normalize_operator_path_fields is new_paths.normalize_operator_path_fields
    assert old_paths.repo_root() == new_paths.repo_root()
    assert old_run_ledger.append_run_record is new_run_ledger.append_run_record
    assert old_run_ledger.EventAlphaRunLedgerConfig is new_run_ledger.EventAlphaRunLedgerConfig
    assert old_retention.prune_event_alpha_artifacts is new_retention.prune_event_alpha_artifacts
    assert old_retention.EventAlphaRetentionConfig is new_retention.EventAlphaRetentionConfig
    assert old_locks.acquire_run_lock is new_locks.acquire_run_lock
    assert old_locks.EventAlphaRunLockConfig is new_locks.EventAlphaRunLockConfig
    assert old_locks._read_lock is new_locks._read_lock
    assert old_namespace_status.mark_namespace_stale is new_namespace_status.mark_namespace_stale
    assert old_namespace_status.EventAlphaNamespaceStatus is new_namespace_status.EventAlphaNamespaceStatus


def test_event_alpha_split_runner_and_make_target_are_wired():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    output = subprocess.check_output(
        [sys.executable, str(root / "tests" / "test_indicators.py"), "--list-tests"],
        cwd=root,
        text=True,
    )
    counts = {
        key: int(value)
        for line in output.splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
    }
    assert counts["standalone_tests"] > 600
    assert counts["event_alpha_tests"] > 500

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    assert "test-event-alpha:" in makefile
    assert "$(PYTHON) -m pytest tests/event_alpha" in makefile

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _legacy_helpers as _event_alpha_legacy_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_legacy_helpers).items()
    if not name.startswith("__")
})

def test_event_impact_hypothesis_store_reports_schema_and_promotion_diagnostics():
    import json
    from datetime import datetime, timezone
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import event_impact_hypothesis_store

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    rows = [
        {
            "row_type": "event_impact_hypothesis",
            "schema_version": event_impact_hypothesis_store.IMPACT_HYPOTHESIS_STORE_SCHEMA_VERSION,
            "observed_at": now.isoformat(),
            "run_id": "run-new",
            "hypothesis_id": "current",
            "status": "validation_search_pending",
            "validation_stage": "candidate_assets_suggested",
            "hypothesis_score": 54.0,
            "impact_category": "ai_ipo_proxy",
            "external_asset": "OpenAI",
            "external_entities": [{"name": "OpenAI"}],
            "crypto_candidate_assets": [{"symbol": "VELVET", "coin_id": "velvet", "source": "candidate_discovery_search"}],
            "why_not_promoted": ["candidate_identity_not_validated", "catalyst_link_missing"],
            "generated_queries": [
                {"query": "OpenAI crypto exposure", "query_type": "candidate_discovery"},
                {"query": "VELVET OpenAI exposure", "query_type": "candidate_validation"},
            ],
            "executed_queries": [
                {"query": "OpenAI crypto exposure", "query_type": "candidate_discovery"},
            ],
            "rejected_validation_samples": [{
                "query": "OpenAI crypto exposure",
                "query_type": "candidate_discovery",
                "result_title": "VELVET opens OpenAI venue",
                "source": "fixture",
                "candidate_symbol": "SECTOR",
                "score": 45,
                "result_score": 45,
                "rejection_reason": "result_identity_rejected",
            }],
        },
        {
            "row_type": "event_impact_hypothesis",
            "observed_at": "2026-06-17T12:00:00+00:00",
            "run_id": "run-old",
            "hypothesis_id": "legacy",
            "status": "hypothesis",
            "impact_category": "rwa_preipo_proxy",
            "external_asset": "SpaceX",
            "crypto_candidate_assets": [{"symbol": "OPENAI", "source": "legacy_bad_parse"}],
        },
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_impact_hypotheses.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        all_rows = event_impact_hypothesis_store.load_impact_hypotheses(path)
        report = event_impact_hypothesis_store.format_impact_hypotheses_store_report(all_rows, now=now)
        assert "schema_audit:" in report
        assert "latest_run_id: run-new" in report
        assert "historical_rows_available: 1" in report
        assert "legacy_rows=1" in report
        assert "missing_validation_stage=1" in report
        assert "legacy_schema_missing_stage=1" in report
        assert "entity_audit:" in report
        assert "suspicious_external_as_candidate=1" in report
        assert "generated_query_type_counts: candidate_discovery=1, candidate_validation=1" in report
        assert "executed_query_type_counts: candidate_discovery=1" in report
        assert "Why not promoted diagnostics:" in report
        assert "candidate_identity_not_validated=1" in report
        assert "Rejected validation evidence samples: 1" in report
        latest = event_impact_hypothesis_store.load_impact_hypotheses(path, latest_run=True, include_legacy=False)
        assert latest.rows_read == 1
        assert latest.rows[0]["hypothesis_id"] == "current"
        assert all(row["hypothesis_id"] != "legacy" for row in latest.rows)
        by_run = event_impact_hypothesis_store.load_impact_hypotheses(path, run_id="run-old", include_legacy=True)
        assert by_run.rows_read == 1
        assert by_run.rows[0]["hypothesis_id"] == "legacy"
        since = event_impact_hypothesis_store.load_impact_hypotheses(path, since="2026-06-18T00:00:00+00:00")
        assert since.rows_read == 1


def test_event_llm_source_triage_schema_and_quote_validation():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_source_enrichment
    from crypto_rsi_scanner.event_models import RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMSourceQualityProvider

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)

    def raw_event(raw_id: str, provider: str, url: str, title: str, body: str) -> RawDiscoveredEvent:
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider=provider,
            fetched_at=now,
            published_at=now,
            source_url=url,
            title=title,
            body=body,
            raw_json={},
            source_confidence=0.9,
            content_hash=raw_id,
        )

    provider = FixtureLLMSourceQualityProvider(cases={
        "good-triage": {
            "page_type": "article",
            "is_real_article": True,
            "article_quality": "fixture_text_used",
            "boilerplate_ratio_estimate": 0.08,
            "is_official_source": False,
            "is_recap": False,
            "is_affiliate_or_seo": False,
            "candidate_catalyst_mechanism_present": True,
            "evidence_quote": "Velvet offers SpaceX pre-IPO tokenized stock exposure",
            "confidence": 0.91,
            "reason": "direct mechanism quote",
        },
        "official-triage": {
            "page_type": "official_announcement",
            "is_real_article": True,
            "article_quality": "fixture_text_used",
            "boilerplate_ratio_estimate": 0.05,
            "is_official_source": True,
            "is_recap": False,
            "is_affiliate_or_seo": False,
            "candidate_catalyst_mechanism_present": True,
            "evidence_quote": "Binance will list TESTUSDT",
            "confidence": 0.94,
        },
        "seo-triage": {
            "page_type": "seo_affiliate",
            "is_real_article": True,
            "article_quality": "good",
            "boilerplate_ratio_estimate": 0.2,
            "is_official_source": False,
            "is_recap": False,
            "is_affiliate_or_seo": True,
            "candidate_catalyst_mechanism_present": False,
            "evidence_quote": "",
            "confidence": 0.88,
        },
        "bad-triage": {
            "page_type": "not_a_page_type",
            "is_real_article": True,
            "article_quality": "good",
            "boilerplate_ratio_estimate": 0.1,
            "is_official_source": False,
            "is_recap": False,
            "is_affiliate_or_seo": False,
            "candidate_catalyst_mechanism_present": True,
            "evidence_quote": "unsupported",
            "confidence": 0.8,
        },
        "missing-quote": {
            "page_type": "article",
            "is_real_article": True,
            "article_quality": "fixture_text_used",
            "boilerplate_ratio_estimate": 0.1,
            "is_official_source": False,
            "is_recap": False,
            "is_affiliate_or_seo": False,
            "candidate_catalyst_mechanism_present": True,
            "evidence_quote": "quote not in source",
            "confidence": 0.92,
        },
    })
    cfg = event_source_enrichment.EventSourceQualityJudgeConfig(enabled=True, min_importance_score=0)

    good = event_source_enrichment.run_llm_source_triage(
        raw_event(
            "good-triage",
            "cryptopanic_news",
            "https://fixture.test/velvet",
            "Velvet offers SpaceX exposure",
            "Velvet offers SpaceX pre-IPO tokenized stock exposure for crypto users.",
        ),
        provider=provider,
        cfg=cfg,
    )
    assert good is not None
    assert good.page_type == "article"
    assert good.candidate_catalyst_mechanism_present is True
    assert good.confidence > 0.8

    official = event_source_enrichment.run_llm_source_triage(
        raw_event(
            "official-triage",
            "binance_announcements",
            "https://www.binance.com/en/support/announcement/test",
            "Binance Will List TESTUSDT",
            "Binance will list TESTUSDT and open spot trading.",
        ),
        provider=provider,
        cfg=cfg,
    )
    assert official is not None
    assert official.is_official_source is True

    seo = event_source_enrichment.run_llm_source_triage(
        raw_event(
            "seo-triage",
            "rss",
            "https://seo.example/referral",
            "Register Binance now",
            "Register Binance now with referral code USD777 and sign up now for lifetime fee bonus.",
        ),
        provider=provider,
        cfg=cfg,
    )
    assert seo is not None
    assert seo.is_real_article is False
    assert seo.confidence <= 0.45

    missing = event_source_enrichment.run_llm_source_triage(
        raw_event(
            "missing-quote",
            "rss",
            "https://fixture.test/missing",
            "Velvet offers SpaceX exposure",
            "Velvet offers SpaceX exposure.",
        ),
        provider=provider,
        cfg=cfg,
    )
    assert missing is not None
    assert missing.confidence <= 0.50
    assert "evidence_quote_missing_from_source" in missing.warnings

    try:
        event_source_enrichment.run_llm_source_triage(
            raw_event("bad-triage", "rss", "https://fixture.test/bad", "Bad", "unsupported"),
            provider=provider,
            cfg=cfg,
        )
    except ValueError as exc:
        assert "invalid LLM source page_type" in str(exc)
    else:
        raise AssertionError("invalid LLM source triage enum should fail validation")


def test_official_exchange_activation_schema_for_bybit_and_binance_fixture_artifacts():
    import json

    from crypto_rsi_scanner import (
        config,
        event_alpha_artifact_doctor,
        event_alpha_source_coverage,
        event_official_exchange,
        event_official_exchange_activation,
        event_provider_status,
    )

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        event_official_exchange.run_official_exchange_scan(
            namespace_dir=base,
            provider_paths={
                "binance_announcements": "fixtures/event_discovery/official_exchange_binance_announcements.json",
                "bybit_announcements": "fixtures/event_discovery/official_exchange_bybit_announcements.json",
            },
            profile="fixture",
            artifact_namespace="official_exchange_smoke",
            run_mode="fixture",
            run_id="run-official-activation",
            observed_at="2026-06-15T16:00:00Z",
        )
        activation = event_official_exchange_activation.build_activation_report(
            namespace_dir=base,
            profile="fixture",
            artifact_namespace="official_exchange_smoke",
            observed_at="2026-06-15T16:00:00Z",
        )
        json_path, md_path = event_official_exchange_activation.write_activation_artifacts(activation, base)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        rows = {str(row.get("provider") or ""): row for row in payload["providers"]}

        assert set(event_official_exchange_activation.SHARED_SCHEMA_FIELDS) <= set(rows["bybit_announcements_public"])
        assert set(event_official_exchange_activation.SHARED_SCHEMA_FIELDS) <= set(rows["binance_announcements_public_or_fixture"])
        assert set(event_official_exchange_activation.SHARED_SCHEMA_FIELDS) <= set(rows["binance_announcements_signed_listener"])
        assert rows["bybit_announcements_public"]["mode"] == "public_http_no_key"
        assert rows["bybit_announcements_public"]["configured"] is True
        assert rows["bybit_announcements_public"]["provider_health_status"] == "fixture_ready"
        assert rows["bybit_announcements_public"]["official_events_written"] >= 1
        assert rows["binance_announcements_public_or_fixture"]["mode"] == "public_or_fixture_parser"
        assert rows["binance_announcements_public_or_fixture"]["configured"] is True
        assert rows["binance_announcements_public_or_fixture"]["live_call_allowed"] is False
        assert rows["binance_announcements_public_or_fixture"]["provider_health_status"] == "fixture_ready"
        assert rows["binance_announcements_public_or_fixture"]["official_events_written"] >= 1
        assert rows["binance_announcements_signed_listener"]["mode"] == "signed_websocket_listener"
        assert rows["binance_announcements_signed_listener"]["configured"] is False
        assert rows["binance_announcements_signed_listener"]["live_call_allowed"] is False
        assert rows["binance_announcements_signed_listener"]["skip_reason"] == "blocked_without_signed_listener_env"
        assert all(row["strict_alerts_created"] == 0 for row in rows.values())
        assert all(row["telegram_sends"] == 0 for row in rows.values())
        assert "Binance public/fixture second" in md_path.read_text(encoding="utf-8")

        coverage = event_alpha_source_coverage.build_source_coverage_report(
            provider_status_report=event_provider_status.build_event_discovery_provider_status(config),
            provider_health_rows={},
            profile="fixture",
            artifact_namespace="official_exchange_smoke",
            artifact_namespace_dir=base,
        )
        coverage_text = event_alpha_source_coverage.format_source_coverage_report(coverage)
        official_pack = next(pack for pack in coverage.packs if pack.source_pack == "official_exchange_listing_pack")
        assert "bybit_announcements_public" in official_pack.healthy_providers
        assert "binance_announcements_public_or_fixture" in official_pack.healthy_providers
        assert "binance_announcements_signed_listener" in official_pack.missing_providers
        assert "bybit_announcements_public mode=public_http_no_key" in coverage_text
        assert "binance_announcements_public_or_fixture mode=public_or_fixture_parser" in coverage_text
        assert "binance_announcements_signed_listener mode=signed_websocket_listener" in coverage_text
        assert "binance_announcements_public_or_fixture" in coverage_text
        assert "Binance requires API key" not in coverage_text

        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            inspected_alert_store_path=base / "event_alpha_alerts.jsonl",
            source_coverage_report_path=base / "event_alpha_source_coverage.md",
            profile="fixture",
            artifact_namespace="official_exchange_smoke",
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor.official_exchange_activation_missing_shared_schema == 0
        assert doctor.official_exchange_activation_live_without_ledger == 0
        assert doctor.official_exchange_activation_signed_listener_secret_leak == 0
        assert doctor.official_exchange_activation_forbidden_side_effect_claim == 0


def test_event_alpha_consolidation_import_shims_and_schema_registry():
    import crypto_rsi_scanner.event_integrated_radar as old_integrated_radar
    import crypto_rsi_scanner.event_market_anomaly_scanner as old_market_anomaly
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
    from crypto_rsi_scanner.event_alpha.artifacts import paths as new_paths
    from crypto_rsi_scanner.event_alpha.doctor import schema_doctor
    from crypto_rsi_scanner.event_alpha.radar import integrated_radar as new_integrated_radar
    from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner as new_market_anomaly
    from crypto_rsi_scanner.event_artifact_paths import artifact_display_path

    assert new_integrated_radar.run_integrated_radar_cycle is old_integrated_radar.run_integrated_radar_cycle
    assert new_market_anomaly.scan_market_rows is old_market_anomaly.scan_market_rows
    assert new_paths.artifact_display_path is artifact_display_path
    required = {
        "core_opportunity_v1",
        "integrated_radar_candidate_v1",
        "notification_delivery_v1",
        "integrated_notification_delivery_v1",
        "source_coverage_v1",
        "provider_readiness_v1",
        "provider_preflight_v1",
        "coinalyze_request_ledger_v1",
        "derivatives_state_snapshot_v1",
        "derivatives_crowding_candidate_v1",
        "fade_review_candidate_v1",
        "market_state_snapshot_v1",
        "market_anomaly_v1",
        "official_exchange_event_v1",
        "scheduled_catalyst_event_v1",
        "unlock_event_v1",
        "outcome_row_v1",
        "calibration_prior_v1",
        "namespace_status_v1",
        "run_ledger_v1",
    }
    assert required.issubset(schema_v1.SCHEMAS)
    assert schema_v1.EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION == "event_alpha_schema_v1"
    assert schema_doctor.check_registry_schema_dependency_errors() == ()


def test_event_alpha_schema_v1_validation_policy():
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1

    schema = schema_v1.get_schema("integrated_radar_candidate_v1")
    valid = {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "iar:test",
        "symbol": "TEST",
        "opportunity_type": "CONFIRMED_LONG_RESEARCH",
        "research_only": True,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
    }
    assert schema_v1.validate_row_against_schema(valid, schema) == []

    missing = dict(valid)
    missing.pop("candidate_id")
    assert "missing_required_field:candidate_id" in schema_v1.validate_row_against_schema(missing, schema)

    invalid_enum = dict(valid, opportunity_type="BUY_NOW")
    assert any(error.startswith("invalid_enum:opportunity_type") for error in schema_v1.validate_row_against_schema(invalid_enum, schema))

    path_schema = schema_v1.get_schema("core_opportunity_v1")
    bad_path = {
        "row_type": "event_core_opportunity",
        "core_opportunity_id": "agg:test",
        "symbol": "TEST",
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "research_card_path": "/tmp/local-card.md",
    }
    assert "absolute_non_debug_path:research_card_path" in schema_v1.validate_row_against_schema(bad_path, path_schema)
    debug_abs = dict(bad_path, research_card_path="event_fade_cache/unit/card.md", research_card_path_abs_debug="/tmp/local-card.md")
    assert "absolute_non_debug_path:research_card_path" not in schema_v1.validate_row_against_schema(debug_abs, path_schema)


def test_event_alpha_cli_package_and_make_targets_are_available():
    from crypto_rsi_scanner.cli.dispatch import dispatch_command_name
    from crypto_rsi_scanner.cli.parser import build_parser, command_group, dispatch_key_from_args
    from crypto_rsi_scanner.cli.main import main as cli_main

    root = _event_alpha_legacy_helpers.REPO_ROOT
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    assert callable(cli_main)
    parser = build_parser()
    default_args = parser.parse_args([])
    assert default_args.top_n is None
    assert default_args.dry_run is False
    assert dispatch_key_from_args(default_args) == "run_scan"
    preview_args = parser.parse_args(["--event-alpha-notify-preview", "--event-alpha-profile", "notify_no_key"])
    assert preview_args.event_alpha_notify_preview is True
    assert preview_args.event_alpha_profile == "notify_no_key"
    assert dispatch_key_from_args(preview_args) == "event_alpha_notify_preview"
    assert dispatch_command_name(["--event-alpha-integrated-radar-smoke"]) == "event_alpha_integrated_radar_smoke"
    assert dispatch_command_name(["--event-alpha-artifact-doctor"]) == "event_alpha_artifact_doctor"
    assert command_group(["-m", "crypto_rsi_scanner.backtest"]) == "backtest"
    assert command_group(["--event-alpha-live-provider-readiness"]) == "event_alpha_provider_readiness"
    assert command_group(["--event-alpha-coinalyze-no-send-rehearsal"]) == "event_alpha_coinalyze"
    assert command_group(["--event-alpha-bybit-announcements-preflight"]) == "event_alpha_official_exchange"
    assert dispatch_command_name(["--event-alpha-namespace-lifecycle-report"]) == "event_alpha_namespace_lifecycle_report"
    assert "test-pytest:" in makefile
    assert "test-pytest-parallel:" in makefile
    assert "event-alpha-namespace-lifecycle-report:" in makefile
    assert "event-alpha-list-active-namespaces:" in makefile
    assert "event-alpha-archive-stale-namespaces:" in makefile
