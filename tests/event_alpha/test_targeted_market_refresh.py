"""Focused Event Alpha targeted-market refresh tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_targeted_market_refresh_batches_unique_assets_by_priority_and_preserves_snapshots(tmp_path):
    import json
    from datetime import datetime, timezone
    from types import SimpleNamespace
    import crypto_rsi_scanner.event_alpha.artifacts.schema_v1 as event_schema_v1
    import crypto_rsi_scanner.event_alpha.doctor.checks.operations as doctor_operations
    import crypto_rsi_scanner.event_alpha.radar.near_miss as event_near_miss

    snapshot_path = tmp_path / "event_market_state_snapshots.jsonl"
    existing_current = {
        "row_type": "event_market_state_snapshot",
        "run_id": "run-1",
        "symbol": "OLD",
        "coin_id": "old",
        "canonical_asset_id": "old",
    }
    existing_other = {
        **existing_current,
        "run_id": "run-0",
        "symbol": "OLDER",
        "coin_id": "older",
        "canonical_asset_id": "older",
    }
    snapshot_path.write_text(
        json.dumps(existing_current) + "\n" + json.dumps(existing_other) + "\n",
        encoding="utf-8",
    )
    rows = (
        {
            "candidate_id": "family-alpha-low",
            "symbol": "ALPHA",
            "coin_id": "alpha",
            "canonical_asset_id": "alpha",
            "score": 60,
            "source_class": "market_anomaly",
            "market_context_freshness_status": "missing",
        },
        {
            "candidate_id": "family-alpha-accepted",
            "symbol": "ALPHA",
            "coin_id": "alpha",
            "canonical_asset_id": "alpha",
            "score": 58,
            "accepted_evidence_count": 1,
            "market_context_freshness_status": "missing",
        },
        {
            "candidate_id": "family-beta-near",
            "symbol": "BETA",
            "coin_id": "beta",
            "canonical_asset_id": "beta",
            "score": 64,
            "market_context_freshness_status": "missing",
        },
        {
            "candidate_id": "family-gamma-official",
            "symbol": "GAMMA",
            "coin_id": "gamma",
            "canonical_asset_id": "gamma",
            "score": 40,
            "source_class": "official_exchange",
            "market_context_freshness_status": "missing",
        },
    )

    class BatchProvider:
        name = "fixture_batch_market"

        def __init__(self):
            self.calls = []

        def fetch_market_rows(self, coin_ids, *, max_assets, timeout_seconds):
            ids = tuple(coin_ids)
            self.calls.append((ids, max_assets, timeout_seconds))
            return ([
                {
                    "id": coin_id,
                    "symbol": coin_id,
                    "current_price": 2.0,
                    "return_unit": "percent_points",
                    "return_4h": 12,
                    "return_24h": 18,
                    "relative_return_vs_btc_4h": 10,
                    "volume_zscore_24h": 3,
                    "liquidity_usd": 10_000_000,
                    "freshness_status": "fresh",
                    "source": "fixture_batch_market",
                }
                for coin_id in ids
            ], ())

    provider = BatchProvider()
    result = event_near_miss.run_targeted_market_refresh(
        rows,
        namespace_dir=tmp_path,
        profile="fixture",
        artifact_namespace="targeted",
        run_mode="candidate_mode",
        run_id="run-1",
        provider=provider,
        cfg=event_near_miss.EventNearMissConfig(
            market_refresh_enabled=True,
            max_market_refresh_assets=20,
            market_refresh_timeout_seconds=3.0,
        ),
        enabled=True,
        now=datetime(2026, 7, 11, 12, tzinfo=timezone.utc),
    )

    assert len(provider.calls) == 1
    requested, max_assets, timeout_seconds = provider.calls[0]
    assert requested == ("alpha", "beta", "gamma")
    assert max_assets == 3
    assert timeout_seconds == 3.0
    assert result.queue[0].priority_bucket == "accepted_evidence"
    assert set(result.queue[0].candidate_family_ids) == {
        "family-alpha-accepted",
        "family-alpha-low",
    }
    assert result.request_count == 1
    assert result.refreshed_assets == 3
    persisted = [
        json.loads(line)
        for line in snapshot_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {(row["run_id"], row["canonical_asset_id"]) for row in persisted} >= {
        ("run-1", "old"),
        ("run-0", "older"),
        ("run-1", "alpha"),
        ("run-1", "beta"),
        ("run-1", "gamma"),
    }
    assert result.persisted_snapshot_rows == 4
    assert all(
        row["telegram_sends"] == 0 and row["trades_created"] == 0
        for row in result.ledger_rows
    )
    for artifact in (result.ledger_path, result.report_json_path, snapshot_path):
        assert event_schema_v1.validate_artifact_file(artifact)["errors"] == []
    blockers = []
    doctor_operations._check_targeted_market_refresh(  # noqa: SLF001 - focused contract regression
        SimpleNamespace(namespace_dir=tmp_path),
        blockers,
    )
    assert blockers == []


def test_integrated_targeted_market_refresh_propagates_to_core_cards_without_source_only_promotion(tmp_path):
    import json
    import os
    from datetime import datetime, timezone
    from unittest.mock import patch
    from crypto_rsi_scanner import config
    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as event_integrated_radar

    env_names = (
        "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "RSI_EVENT_ALPHA_RUN_LEDGER_PATH",
        "RSI_EVENT_CORE_OPPORTUNITY_STORE_PATH",
        "RSI_EVENT_RESEARCH_CARDS_DIR",
        "RSI_EVENT_ALPHA_DAILY_BRIEF_PATH",
        "RSI_EVENT_PROVIDER_HEALTH_PATH",
    )
    namespace = "targeted_integrated"
    namespace_dir = tmp_path / namespace
    namespace_dir.mkdir(parents=True)
    official_event = {
        "row_type": "official_exchange_event",
        "official_exchange_event_id": "official-alpha",
        "provider": "bybit_announcements",
        "exchange": "bybit",
        "event_type": "spot_listing",
        "title": "Bybit will list Alpha (ALPHA)",
        "source_url": "https://announcements.bybit.com/alpha",
        "published_at": "2026-07-11T10:00:00+00:00",
        "symbols": ["ALPHA"],
        "coin_ids": ["alpha"],
        "source_class": "official_exchange",
        "source_pack": "official_exchange_listing_pack",
    }
    official_candidate = {
        **official_event,
        "row_type": "official_listing_candidate",
        "candidate_id": "official-alpha-candidate",
        "symbol": "ALPHA",
        "coin_id": "alpha",
        "canonical_asset_id": "alpha",
        "accepted_evidence_count": 1,
        "evidence_acquisition_status": "accepted_evidence_found",
    }
    anomaly = {
        "row_type": "event_market_anomaly",
        "market_anomaly_id": "anomaly-beta",
        "symbol": "BETA",
        "coin_id": "beta",
        "canonical_asset_id": "beta",
        "market_state_class": "no_reaction",
        "source_class": "market_anomaly",
        "source_pack": "market_anomaly_pack",
        "no_alert_until_evidence": True,
    }
    (namespace_dir / "event_official_exchange_events.jsonl").write_text(
        json.dumps(official_event) + "\n",
        encoding="utf-8",
    )
    (namespace_dir / "event_official_listing_candidates.jsonl").write_text(
        json.dumps(official_candidate) + "\n",
        encoding="utf-8",
    )
    (namespace_dir / "event_market_anomalies.jsonl").write_text(
        json.dumps(anomaly) + "\n",
        encoding="utf-8",
    )

    class BreakoutProvider:
        name = "fixture_targeted_market"

        def fetch_market_rows(self, coin_ids, *, max_assets, timeout_seconds):
            del max_assets, timeout_seconds
            return ([
                {
                    "id": coin_id,
                    "symbol": coin_id,
                    "current_price": 2.0,
                    "return_unit": "percent_points",
                    "return_4h": 12,
                    "return_24h": 18,
                    "relative_return_vs_btc_4h": 10,
                    "volume_zscore_24h": 3,
                    "liquidity_usd": 10_000_000,
                    "spread_bps": 20,
                    "freshness_status": "fresh",
                    "source": "fixture_targeted_market",
                }
                for coin_id in coin_ids
            ], ())

    with (
        patch.dict(os.environ, {name: "" for name in env_names}),
        patch.object(config, "EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED", True),
        patch.object(config, "EVENT_ALPHA_TARGETED_MARKET_REFRESH_MAX_ASSETS", 20),
        patch.object(config, "EVENT_ALPHA_TARGETED_MARKET_REFRESH_TIMEOUT_SECONDS", 3.0),
    ):
        context = event_alpha_artifacts.context_from_profile(
            "fixture",
            run_mode="candidate_mode",
            base_dir=tmp_path,
            artifact_namespace=namespace,
        )
        result = event_integrated_radar.run_integrated_radar_cycle(
            context=context,
            fixture=False,
            input_mode=event_integrated_radar.INPUT_MODE_LOAD_EXISTING,
            observed_at=datetime(2026, 7, 11, 12, tzinfo=timezone.utc),
            targeted_market_provider=BreakoutProvider(),
        )

    candidates = [
        json.loads(line)
        for line in result.integrated_candidates_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_symbol = {row["symbol"]: row for row in candidates}
    assert by_symbol["ALPHA"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
    assert by_symbol["BETA"]["opportunity_type"] == "UNCONFIRMED_RESEARCH"
    assert by_symbol["ALPHA"]["market_refresh_success"] is True
    assert by_symbol["ALPHA"]["market_refresh_artifact"]
    core_rows = [
        json.loads(line)
        for line in Path(result.core_opportunity_store_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    alpha_core = next(row for row in core_rows if row.get("symbol") == "ALPHA")
    assert alpha_core["market_refresh_success"] is True
    assert alpha_core["market_refresh_artifact"]
    card_text = next(
        path.read_text(encoding="utf-8")
        for path in result.research_card_paths
        if "ALPHA" in path.read_text(encoding="utf-8")
    )
    assert "Market refresh artifact:" in card_text
    assert "event_targeted_market_refresh_report.json" in card_text
    report = json.loads(
        (namespace_dir / "event_targeted_market_refresh_report.json").read_text(encoding="utf-8")
    )
    assert report["request_count"] == 1
    assert report["telegram_sends"] == 0
    assert report["trades_created"] == 0
    assert report["paper_trades_created"] == 0
    assert report["normal_rsi_signal_rows_written"] == 0
    assert report["triggered_fade_created"] == 0
