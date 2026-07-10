"""Focused Event Alpha provider adapter tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


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


def test_event_alpha_dex_onchain_readiness_artifacts_are_fixture_only_and_covered():
    import json
    from datetime import datetime, timezone

    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.radar.source_coverage as event_alpha_source_coverage
    import crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness as event_dex_onchain_readiness

    root = _event_alpha_api_helpers.REPO_ROOT
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        result = event_dex_onchain_readiness.run_dex_onchain_readiness(
            namespace_dir=base,
            profile="fixture",
            artifact_namespace="dex_onchain_readiness_smoke",
            geckoterminal_path=root / "fixtures/event_dex_onchain/geckoterminal_pools.json",
            coingecko_dex_path=root / "fixtures/event_dex_onchain/coingecko_dex_pools.json",
            defillama_path=root / "fixtures/event_dex_onchain/defillama_protocol_fundamentals.json",
            smoke_mode=True,
            now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
        )
        payload = json.loads(result.readiness_json_path.read_text(encoding="utf-8"))
        assert payload["readiness_status"] == "fixture_ready"
        assert payload["live_call_allowed"] is False
        assert payload["no_send_rehearsal"] is True
        assert payload["telegram_sends"] == 0
        assert payload["trades_created"] == 0
        assert payload["paper_trades_created"] == 0
        assert payload["normal_rsi_signal_rows_written"] == 0
        assert payload["triggered_fade_created"] == 0
        by_provider = {row["provider"]: row for row in payload["providers"]}
        assert set(by_provider) == {"geckoterminal", "coingecko_dex", "defillama_tvl_fees_revenue"}
        assert all(row["fixture_parser_status"] == "pass" for row in by_provider.values())
        assert payload["dex_pool_state_rows"] == 3
        assert payload["dex_pool_anomaly_rows"] == 3
        assert payload["protocol_fundamental_rows"] == 2
        assert payload["classification_counts"]["dex_liquidity_expansion"] == 2
        assert payload["classification_counts"]["suspicious_low_liquidity_pump"] == 1
        assert payload["classification_counts"]["protocol_revenue_tvl_growth"] == 1
        assert payload["classification_counts"]["protocol_fundamentals_deterioration"] == 1

        state_rows = event_dex_onchain_readiness.load_dex_pool_state(base)
        anomaly_rows = event_dex_onchain_readiness.load_dex_pool_anomalies(base)
        protocol_rows = event_dex_onchain_readiness.load_protocol_fundamentals(base)
        assert {row["canonical_asset_id"] for row in state_rows} >= {"token-b", "token-c"}
        assert any(row["classification"] == "suspicious_low_liquidity_pump" for row in anomaly_rows)
        assert any(row["classification"] == "protocol_revenue_tvl_growth" for row in protocol_rows)
        assert all(row["source_url"] and row["observed_at"] for row in protocol_rows)

        source_report = event_alpha_source_coverage.build_source_coverage_report(
            provider_status_report=event_provider_status.build_event_discovery_provider_status(_event_provider_status_cfg()),
            profile="fixture",
            artifact_namespace="dex_onchain_readiness_smoke",
            artifact_namespace_dir=base,
            now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
        )
        assert source_report.dex_onchain_readiness_status == "fixture_ready"
        assert source_report.dex_pool_state_rows == 3
        assert source_report.dex_pool_anomaly_rows == 3
        assert source_report.protocol_fundamental_rows == 2
        source_text = event_alpha_source_coverage.format_source_coverage_report(source_report)
        assert "DEX/on-chain readiness: fixture_ready" in source_text
        assert "geckoterminal configured=true fixture_parser_status=pass" in source_text
        assert "defillama_tvl_fees_revenue configured=true fixture_parser_status=pass" in source_text
        (base / "event_alpha_source_coverage.md").write_text(source_text, encoding="utf-8")

        clean = event_alpha_artifact_doctor.diagnose_artifacts(
            source_coverage_report_path=base / "event_alpha_source_coverage.md",
            profile="fixture",
            artifact_namespace="dex_onchain_readiness_smoke",
            include_test_artifacts=True,
            strict=True,
        )
        assert clean.dex_onchain_live_without_ledger == 0
        assert clean.dex_low_liquidity_promoted_confirmed == 0
        assert clean.protocol_metric_missing_source_time == 0

        payload["live_call_allowed"] = True
        payload["providers"][0]["live_call_allowed"] = True
        payload["providers"][0]["fixture_parser_status"] = ""
        result.readiness_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        protocol_rows[0].pop("source_url", None)
        result.protocol_fundamentals_path.write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in protocol_rows) + "\n",
            encoding="utf-8",
        )
        unsafe = event_alpha_artifact_doctor.diagnose_artifacts(
            source_coverage_report_path=base / "event_alpha_source_coverage.md",
            profile="fixture",
            artifact_namespace="dex_onchain_readiness_smoke",
            include_test_artifacts=True,
            strict=True,
        )
        assert unsafe.dex_onchain_live_without_ledger >= 1
        assert unsafe.dex_onchain_live_call_allowed_in_smoke >= 1
        assert unsafe.dex_onchain_missing_fixture_parser_status == 1
        assert unsafe.protocol_metric_missing_source_time == 1
        assert unsafe.status == "BLOCKED"


def test_event_discovery_coinalyze_derivatives_provider_parses_fixture():
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.derivatives_providers.coinalyze import CoinalyzeDerivativesProvider

    snapshots = CoinalyzeDerivativesProvider(_derivatives_fixture_path(), required=True).fetch_snapshots()
    assert "testlist" in snapshots
    assert "TESTLIST" in snapshots
    assert "TESTLISTUSDT_PERP" in snapshots
    assert "TEST" not in snapshots
    listing = snapshots["testlist"]
    assert listing["symbol"] == "TESTLIST"
    assert listing["perp_available"] is True
    assert listing["funding_rate_8h"] == 0.0012
    assert listing["perp_spot_volume_ratio"] == 22.0
    assert snapshots["testperp"]["perp_available"] is False

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_derivatives.json"
        bad_path.write_text(json.dumps({"snapshots": ["not an object"]}), encoding="utf-8")
        assert CoinalyzeDerivativesProvider(bad_path).fetch_snapshots() == {}
        try:
            CoinalyzeDerivativesProvider(bad_path, required=True).fetch_snapshots()
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed derivatives fixture should fail")


def test_event_discovery_coinalyze_live_provider_parses_offline():
    import json
    from urllib.parse import parse_qs, urlparse
    from crypto_rsi_scanner.derivatives_providers.coinalyze import CoinalyzeDerivativesProvider

    seen = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def opener(request, timeout):
        parsed = urlparse(request.full_url)
        endpoint = parsed.path.rsplit("/", 1)[-1]
        query = parse_qs(parsed.query)
        header_value = next(
            value
            for key, value in request.headers.items()
            if key.lower() == "api_key"
        )
        seen.append((endpoint, query, header_value, timeout))
        payloads = {
            "open-interest": [
                {"symbol": "TESTLISTUSDT_PERP.A", "value": 18000000, "update": 1781513400},
                {"symbol": "TESTPERPUSDT_PERP.A", "value": 3000000, "update": 1781513400},
            ],
            "funding-rate": [
                {"symbol": "TESTLISTUSDT_PERP.A", "value": 0.0012, "update": 1781513400},
                {"symbol": "TESTPERPUSDT_PERP.A", "value": -0.0002, "update": 1781513400},
            ],
            "predicted-funding-rate": [
                {"symbol": "TESTLISTUSDT_PERP.A", "value": 0.0015, "update": 1781513400},
                {"symbol": "TESTPERPUSDT_PERP.A", "value": -0.0001, "update": 1781513400},
            ],
            "open-interest-history": [
                {
                    "symbol": "TESTLISTUSDT_PERP.A",
                    "history": [{"t": 1781427000, "c": 10000000}, {"t": 1781513400, "c": 18000000}],
                },
                {
                    "symbol": "TESTPERPUSDT_PERP.A",
                    "history": [{"t": 1781427000, "c": 3000000}, {"t": 1781513400, "c": 3000000}],
                },
            ],
            "liquidation-history": [
                {
                    "symbol": "TESTLISTUSDT_PERP.A",
                    "history": [{"t": 1781510000, "l": 1500000, "s": 1000000}],
                }
            ],
            "long-short-ratio-history": [
                {"symbol": "TESTLISTUSDT_PERP.A", "history": [{"t": 1781510000, "r": 1.8}, {"t": 1781513400, "r": 2.1}]}
            ],
            "ohlcv-history": [
                {
                    "symbol": "TESTLISTUSDT_PERP.A",
                    "history": [{"t": 1781510000, "v": 50000000}, {"t": 1781513400, "v": 20000000}],
                }
            ],
        }
        return FakeResponse(payloads[endpoint])

    snapshots = CoinalyzeDerivativesProvider(
        None,
        live_enabled=True,
        api_key="coinalyze-key",
        symbols=("TESTLISTUSDT_PERP.A", "TESTPERPUSDT_PERP.A"),
        base_url="https://example.test/v1/",
        timeout=3.0,
        opener=opener,
        clock=lambda: 1781513400,
        required=True,
    ).fetch_snapshots()

    assert [row[0] for row in seen] == [
        "open-interest",
        "funding-rate",
        "predicted-funding-rate",
        "open-interest-history",
        "liquidation-history",
        "long-short-ratio-history",
        "ohlcv-history",
    ]
    assert all(row[2] == "coinalyze-key" for row in seen)
    assert seen[0][1]["symbols"] == ["TESTLISTUSDT_PERP.A,TESTPERPUSDT_PERP.A"]
    assert seen[0][1]["convert_to_usd"] == ["true"]

    listing = snapshots["TESTLIST"]
    assert listing["symbol"] == "TESTLIST"
    assert listing["open_interest"] == 18000000.0
    assert listing["open_interest_24h_change_pct"] == 0.8
    assert listing["funding_rate_8h"] == 0.0012
    assert listing["predicted_funding_rate"] == 0.0015
    assert listing["funding_rate_unit"] == "decimal_rate"
    assert listing["open_interest_unit"] == "usd_notional"
    assert listing["liquidations_24h"] == 2500000.0
    assert listing["long_short_ratio"] == 2.1
    assert listing["futures_volume_24h"] == 70000000.0
    assert snapshots["TESTPERP"]["open_interest_24h_change_pct"] == 0.0


def test_event_discovery_coinalyze_live_provider_auto_resolves_future_markets_offline():
    import json
    from urllib.parse import parse_qs, urlparse
    from crypto_rsi_scanner.derivatives_providers.coinalyze import CoinalyzeDerivativesProvider

    seen = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def opener(request, timeout):
        parsed = urlparse(request.full_url)
        endpoint = parsed.path.rsplit("/", 1)[-1]
        query = parse_qs(parsed.query)
        seen.append((endpoint, query, timeout))
        payloads = {
            "future-markets": [
                {
                    "symbol": "TESTLISTUSD_PERP.0",
                    "exchange": "SLOW",
                    "base_asset": "TESTLIST",
                    "quote_asset": "USD",
                    "is_perpetual": True,
                    "margined": "COIN",
                },
                {
                    "symbol": "TESTLISTUSDT_PERP.A",
                    "exchange": "BINANCE",
                    "base_asset": "TESTLIST",
                    "quote_asset": "USDT",
                    "is_perpetual": True,
                    "margined": "STABLE",
                },
                {
                    "symbol": "TESTPERPUSDT_PERP.A",
                    "exchange": "BYBIT",
                    "base_asset": "TESTPERP",
                    "quote_asset": "USDT",
                    "is_perpetual": True,
                    "margined": "STABLE",
                },
                {
                    "symbol": "UNRELATEDUSDT_PERP.A",
                    "exchange": "BINANCE",
                    "base_asset": "UNRELATED",
                    "quote_asset": "USDT",
                    "is_perpetual": True,
                    "margined": "STABLE",
                },
            ],
            "open-interest": [
                {"symbol": "TESTLISTUSDT_PERP.A", "value": 18000000, "update": 1781513400},
                {"symbol": "TESTPERPUSDT_PERP.A", "value": 3000000, "update": 1781513400},
            ],
            "funding-rate": [],
            "predicted-funding-rate": [],
            "open-interest-history": [],
            "liquidation-history": [],
            "long-short-ratio-history": [],
            "ohlcv-history": [],
        }
        return FakeResponse(payloads[endpoint])

    snapshots = CoinalyzeDerivativesProvider(
        None,
        live_enabled=True,
        api_key="coinalyze-key",
        base_symbols=("TESTLIST", "TESTPERP"),
        base_url="https://example.test/v1/",
        opener=opener,
        clock=lambda: 1781513400,
        required=True,
    ).fetch_snapshots()

    assert seen[0][0] == "future-markets"
    assert seen[1][0] == "open-interest"
    assert seen[1][1]["symbols"] == ["TESTLISTUSDT_PERP.A,TESTPERPUSDT_PERP.A"]
    assert snapshots["TESTLIST"]["open_interest"] == 18000000.0
    assert snapshots["TESTPERP"]["open_interest"] == 3000000.0
    assert "UNRELATED" not in snapshots


def test_event_discovery_coinalyze_base_symbols_from_assets():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset

    assets = [
        DiscoveredAsset(coin_id="testlist", symbol="TESTLIST", name="Test List", aliases=("Test List",)),
        DiscoveredAsset(coin_id="testperp", symbol="TESTPERPUSDT", name="Test Perp"),
        DiscoveredAsset(coin_id="bad", symbol="", name="Bad", aliases=("not a ticker",)),
    ]
    assert event_discovery._coinalyze_base_symbols(assets) == ("TESTLIST", "TESTPERP")


def test_event_discovery_coinalyze_live_provider_missing_config_fail_soft():
    from crypto_rsi_scanner.derivatives_providers.coinalyze import CoinalyzeDerivativesProvider

    assert CoinalyzeDerivativesProvider(None, live_enabled=True).fetch_snapshots() == {}
    assert CoinalyzeDerivativesProvider(
        None,
        live_enabled=True,
        api_key="coinalyze-key",
    ).fetch_snapshots() == {}


def test_event_discovery_derivatives_enrich_candidates_without_overriding_raw():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_alpha.radar.resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(start, end)
    raw.extend(event_discovery.load_discovery_events(
        None,
        start,
        end,
        binance_announcements_path=binance_path,
        bybit_announcements_path=bybit_path,
    ))
    assets = load_asset_aliases(aliases_path)
    derivatives = event_discovery.load_derivatives_snapshots(_derivatives_fixture_path())
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
        derivatives_by_asset=derivatives,
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}

    listing = by_symbol["TESTLIST"]
    assert listing.fade_candidate.derivatives is not None
    assert listing.fade_candidate.derivatives.open_interest_24h_change_pct == 0.65
    assert listing.fade_candidate.component_scores["derivatives_crowding"] == 100
    assert listing.data_quality["has_derivatives_snapshot"] is True
    assert listing.classification.is_direct_beneficiary is True
    assert listing.fade_signal.signal_type == FadeSignalType.NO_TRADE

    perp = by_symbol["TESTPERP"]
    assert perp.fade_candidate.derivatives is not None
    assert perp.fade_candidate.derivatives.perp_available is False
    assert perp.fade_candidate.component_scores["derivatives_crowding"] == 30
    assert perp.fade_signal.signal_type == FadeSignalType.NO_TRADE

    velvet = by_symbol["TESTVELVET"]
    assert velvet.fade_candidate.derivatives is not None
    assert velvet.fade_candidate.derivatives.open_interest is None
    assert velvet.fade_candidate.derivatives.open_interest_to_market_cap == 0.4
    assert velvet.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED


def test_event_discovery_supply_providers_parse_fixtures():
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner.supply_providers.arkham import ArkhamSupplyProvider
    from crypto_rsi_scanner.supply_providers.dune import DuneSupplyProvider
    from crypto_rsi_scanner.supply_providers.etherscan import EtherscanSupplyProvider
    from crypto_rsi_scanner.supply_providers.tokenomist import TokenomistSupplyProvider

    tokenomist_path, etherscan_path, arkham_path, dune_path = _supply_fixture_paths()
    tokenomist = TokenomistSupplyProvider(tokenomist_path, required=True).fetch_snapshots()
    etherscan = EtherscanSupplyProvider(etherscan_path, required=True).fetch_snapshots()
    arkham = ArkhamSupplyProvider(arkham_path, required=True).fetch_snapshots()
    dune = DuneSupplyProvider(dune_path, required=True).fetch_snapshots()
    assert tokenomist["testprediction"]["unlock_pct_circulating"] == 0.08
    assert tokenomist["TESTPRED"]["unlock_amount"] == 1800000.0
    assert tokenomist["testvelvet"]["unlock_pct_circulating"] == 0.0
    assert tokenomist["TESTVELVET"]["top_holder_concentration"] == 0.10
    assert etherscan["testlist"]["large_holder_exchange_inflow"] is True
    assert etherscan["TESTLIST"]["cex_inflow_pct_supply"] == 0.04
    assert arkham["testai"]["team_or_mm_wallet_activity"] is True
    assert dune["testfan"]["admin_or_mint_risk"] is True

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_supply.json"
        bad_path.write_text(json.dumps({"snapshots": ["not an object"]}), encoding="utf-8")
        assert TokenomistSupplyProvider(bad_path).fetch_snapshots() == {}
        try:
            TokenomistSupplyProvider(bad_path, required=True).fetch_snapshots()
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed supply fixture should fail")


def test_event_discovery_supply_enriches_without_overriding_raw_or_bypassing_gates():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_alpha.radar.resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, _bybit_path = _exchange_announcement_fixture_paths()
    _cryptopanic_path, _gdelt_path, _blog_path = _news_fixture_paths()
    _ipo_path, _sports_path, prediction_path = _external_catalyst_fixture_paths()
    tokenomist_path, etherscan_path, arkham_path, dune_path = _supply_fixture_paths()
    start = datetime(2026, 6, 13, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(start, end)
    raw.extend(event_discovery.load_discovery_events(
        None,
        start,
        end,
        binance_announcements_path=binance_path,
        prediction_market_events_path=prediction_path,
    ))
    assets = load_asset_aliases(aliases_path)
    supply = event_discovery.load_supply_snapshots(
        tokenomist_supply_path=tokenomist_path,
        etherscan_supply_path=etherscan_path,
        arkham_supply_path=arkham_path,
        dune_supply_path=dune_path,
    )
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
        supply_by_asset=supply,
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}

    listing = by_symbol["TESTLIST"]
    assert listing.fade_candidate.supply is not None
    assert listing.fade_candidate.supply.large_holder_exchange_inflow is True
    assert listing.fade_candidate.component_scores["supply_pressure"] >= 60
    assert listing.classification.is_direct_beneficiary is True
    assert listing.fade_signal.signal_type == FadeSignalType.NO_TRADE

    pred = by_symbol["TESTPRED"]
    assert pred.fade_candidate.supply is not None
    assert pred.fade_candidate.supply.unlock_pct_circulating == 0.08
    assert pred.data_quality["has_supply_snapshot"] is True
    assert pred.fade_signal.signal_type in {FadeSignalType.NO_TRADE, FadeSignalType.WATCHLIST}

    velvet = by_symbol["TESTVELVET"]
    assert velvet.fade_candidate.supply is not None
    assert velvet.fade_candidate.supply.top_holder_concentration == 0.62
    assert velvet.fade_candidate.supply.unlock_pct_circulating is None
    assert velvet.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED
