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


def test_event_discovery_manual_provider_fixture_and_missing_path():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider

    events_path, _ = _event_discovery_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    events = ManualJsonEventProvider(events_path, required=True).fetch_events(start, end)
    assert len(events) == 6
    assert events[0].content_hash
    assert events[0].published_at <= events[0].fetched_at
    assert ManualJsonEventProvider(Path("/definitely/missing.json")).fetch_events(start, end) == []

    try:
        ManualJsonEventProvider(Path("/definitely/missing.json"), required=True).fetch_events(start, end)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("required missing manual fixture should fail")

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad.json"
        bad_path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
        assert ManualJsonEventProvider(bad_path).fetch_events(start, end) == []

        try:
            ManualJsonEventProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed manual fixture should fail")


def test_event_discovery_coingecko_universe_provider_uses_hygiene():
    from crypto_rsi_scanner.event_providers.coingecko_universe import CoinGeckoUniverseProvider

    assets = CoinGeckoUniverseProvider(_coingecko_universe_fixture_path(), required=True).fetch_assets()
    by_id = {asset.coin_id: asset for asset in assets}
    assert set(by_id) == {"bitcoin", "ethereum", "solana"}
    assert by_id["bitcoin"].symbol == "BTC"
    assert by_id["bitcoin"].price == 68000.0
    assert by_id["bitcoin"].source == "coingecko_universe"
    assert "tether" not in by_id


def test_event_discovery_coingecko_universe_provider_can_fetch_live_offline():
    from crypto_rsi_scanner.event_providers.coingecko_universe import CoinGeckoUniverseProvider

    calls = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def get_top_markets(self, n):
            calls.append(n)
            return [
                {
                    "id": "bitcoin",
                    "symbol": "btc",
                    "name": "Bitcoin",
                    "current_price": 68000.0,
                    "market_cap": 1300000000000.0,
                    "total_volume": 35000000000.0,
                    "price_change_percentage_24h_in_currency": 1.2,
                },
                {
                    "id": "tether",
                    "symbol": "usdt",
                    "name": "Tether",
                    "current_price": 1.0,
                    "market_cap": 110000000000.0,
                    "total_volume": 60000000000.0,
                    "price_change_percentage_24h_in_currency": 0.01,
                },
                {
                    "id": "ethereum",
                    "symbol": "eth",
                    "name": "Ethereum",
                    "current_price": 3600.0,
                    "market_cap": 430000000000.0,
                    "total_volume": 18000000000.0,
                    "price_change_percentage_24h_in_currency": -0.8,
                },
                {
                    "id": "solana",
                    "symbol": "sol",
                    "name": "Solana",
                    "current_price": 160.0,
                    "market_cap": 75000000000.0,
                    "total_volume": 4500000000.0,
                    "price_change_percentage_24h_in_currency": 3.4,
                },
            ]

    assets = CoinGeckoUniverseProvider(
        None,
        live_enabled=True,
        limit=2,
        live_fetch_limit=4,
        client_factory=lambda: FakeClient(),
        required=True,
    ).fetch_assets()

    assert calls == [4]
    assert [asset.coin_id for asset in assets] == ["bitcoin", "ethereum"]
    assert assets[0].symbol == "BTC"
    assert assets[1].price == 3600.0


def test_event_discovery_coingecko_universe_provider_live_fail_soft():
    from crypto_rsi_scanner.event_providers.coingecko_universe import CoinGeckoUniverseProvider

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def get_top_markets(self, _n):
            raise TimeoutError("fixture timeout")

    assert CoinGeckoUniverseProvider(
        None,
        live_enabled=True,
        client_factory=lambda: FailingClient(),
    ).fetch_assets() == []


def test_event_discovery_exchange_announcement_providers_parse_fixtures():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.binance_announcements import BinanceAnnouncementProvider
    from crypto_rsi_scanner.event_providers.bybit_announcements import BybitAnnouncementProvider

    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    binance_events = BinanceAnnouncementProvider(binance_path, required=True).fetch_events(start, end)
    bybit_events = BybitAnnouncementProvider(bybit_path, required=True).fetch_events(start, end)
    assert len(binance_events) == 1
    assert len(bybit_events) == 1
    assert binance_events[0].provider == "binance_announcements"
    assert binance_events[0].raw_json["event"]["event_type"] == "exchange_listing"
    assert binance_events[0].raw_json["event"]["event_time"] == "2026-06-15T12:00:00+00:00"
    assert binance_events[0].raw_json["source_class"] == "official_exchange"
    assert binance_events[0].raw_json["exchange"] == "binance"
    assert binance_events[0].raw_json["announcement_symbols"] == ("TESTLIST",)
    assert binance_events[0].raw_json["announcement_pairs"] == ("TESTLIST/USDT",)
    assert binance_events[0].raw_json["announcement_time"] == "2026-06-15T12:00:00+00:00"
    assert binance_events[0].raw_json["source_url"] == "https://www.binance.com/en/support/announcement/binance-testlist"
    assert bybit_events[0].provider == "bybit_announcements"
    assert bybit_events[0].raw_json["event"]["event_type"] == "perp_listing"
    assert bybit_events[0].raw_json["source_class"] == "official_exchange"
    assert bybit_events[0].raw_json["exchange"] == "bybit"
    assert bybit_events[0].raw_json["announcement_symbols"] == ("TESTPERP",)
    assert bybit_events[0].raw_json["announcement_pairs"] == ("TESTPERP/USDT",)
    assert bybit_events[0].raw_json["announcement_contracts"] == ("TESTPERPUSDT",)
    assert bybit_events[0].raw_json["exchange_product_type"] == "perp_listing"

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_announcements.json"
        bad_path.write_text(json.dumps({"result": {"list": ["not an object"]}}), encoding="utf-8")
        assert BinanceAnnouncementProvider(bad_path).fetch_events(start, end) == []
        try:
            BinanceAnnouncementProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed announcement fixture should fail")
        normalized_path = Path(tmp) / "normalized_announcements.json"
        normalized_path.write_text(json.dumps({
            "announcements": [
                {
                    "id": "binance-old-delist",
                    "title": "Binance Will Delist OLDUSDT",
                    "body": "Binance will delist OLD/USDT spot trading pairs.",
                    "publishDate": "2026-06-15T08:00:00Z",
                    "url": "https://www.binance.com/en/support/announcement/old-delist",
                },
                {
                    "id": "binance-new-launchpool",
                    "title": "Binance Launchpool Adds New Token (NEW)",
                    "body": "Binance Launchpool opens NEW subscriptions.",
                    "publishDate": "2026-06-15T08:30:00Z",
                    "url": "https://www.binance.com/en/support/announcement/new-launchpool",
                },
                {
                    "id": "binance-maintenance",
                    "title": "Binance Updates API Rate Limits",
                    "body": "General operational update.",
                    "publishDate": "2026-06-15T09:00:00Z",
                },
            ]
        }), encoding="utf-8")
        normalized = BinanceAnnouncementProvider(normalized_path, required=True).fetch_events(start, end)
        assert [event.raw_json["event"]["event_type"] for event in normalized] == [
            "exchange_delisting",
            "exchange_product_event",
        ]
        assert normalized[0].raw_json["exchange_product_type"] == "delisting"
        assert normalized[0].raw_json["announcement_pairs"] == ("OLD/USDT",)
        assert normalized[1].raw_json["exchange_product_type"] == "launchpool"


def test_event_discovery_binance_cms_websocket_payload_fixture():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.binance_announcements import BinanceAnnouncementProvider

    payload = {
        "type": "DATA",
        "topic": "com_announcement_en",
        "data": json.dumps({
            "catalogId": 48,
            "catalogName": "New Cryptocurrency Listing",
            "publishDate": 1781514000000,
            "title": "Binance Will List Test Live (TLIVE)",
            "body": "Binance will list Test Live and open spot trading for TLIVE/USDT.",
            "disclaimer": "Trade on-the-go.",
        }),
    }
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 16, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "binance_cms_payload.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        events = BinanceAnnouncementProvider(path, required=True).fetch_events(start, end)
    assert len(events) == 1
    event = events[0]
    assert event.provider == "binance_announcements"
    assert event.title == "Binance Will List Test Live (TLIVE)"
    assert event.published_at.isoformat() == "2026-06-15T09:00:00+00:00"
    assert event.raw_json["topic"] == "com_announcement_en"
    assert event.raw_json["message_type"] == "DATA"
    assert event.raw_json["catalogName"] == "New Cryptocurrency Listing"
    assert event.raw_json["event"]["event_type"] == "exchange_listing"
    assert event.raw_json["event"]["event_time"] == "2026-06-15T09:00:00+00:00"
    assert event.raw_json["event"]["event_time_confidence"] == 0.60


def test_event_discovery_binance_live_websocket_provider_parses_offline():
    import hashlib
    import hmac
    import json
    from datetime import datetime, timezone

    import aiohttp

    from crypto_rsi_scanner.event_providers.binance_announcements import BinanceAnnouncementProvider

    payload = {
        "type": "DATA",
        "topic": "com_announcement_en",
        "data": json.dumps({
            "catalogId": 48,
            "catalogName": "New Cryptocurrency Listing",
            "publishDate": 1781514000000,
            "title": "Binance Will List Test Live (TLIVE)",
            "body": "Binance will list Test Live and open spot trading for TLIVE/USDT.",
        }),
    }
    messages = [
        type("Msg", (), {"type": aiohttp.WSMsgType.TEXT, "data": json.dumps({"type": "COMMAND", "code": "000000"})}),
        type("Msg", (), {"type": aiohttp.WSMsgType.TEXT, "data": json.dumps(payload)}),
        type("Msg", (), {"type": aiohttp.WSMsgType.CLOSED, "data": ""}),
    ]
    seen = {}

    class FakeWs:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def receive(self):
            return messages.pop(0)

    class FakeSession:
        def __init__(self, **kwargs):
            seen["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def ws_connect(self, url, *, headers=None, heartbeat=None):
            seen["url"] = url
            seen["headers"] = headers
            seen["heartbeat"] = heartbeat
            return FakeWs()

    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 16, tzinfo=timezone.utc)
    events = BinanceAnnouncementProvider(
        None,
        live_enabled=True,
        api_key="binance-key",
        api_secret="binance-secret",
        ws_url="wss://example.test/sapi/wss",
        listen_seconds=1,
        session_factory=FakeSession,
        clock=lambda: 1781514000.0,
        random_factory=lambda: "fixed-random",
        required=True,
    ).fetch_events(start, end)

    signed_payload = "random=fixed-random&topic=com_announcement_en&recvWindow=30000&timestamp=1781514000000"
    signature = hmac.new(b"binance-secret", signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    assert seen["url"] == f"wss://example.test/sapi/wss?{signed_payload}&signature={signature}"
    assert seen["headers"] == {"X-MBX-APIKEY": "binance-key"}
    assert seen["heartbeat"] == 30.0
    assert len(events) == 1
    assert events[0].provider == "binance_announcements"
    assert events[0].title == "Binance Will List Test Live (TLIVE)"
    assert events[0].raw_json["message_type"] == "DATA"
    assert events[0].raw_json["event"]["event_type"] == "exchange_listing"


def test_event_discovery_binance_live_websocket_missing_credentials_fail_soft():
    from datetime import datetime, timezone
    from crypto_rsi_scanner.event_providers.binance_announcements import BinanceAnnouncementProvider

    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 16, tzinfo=timezone.utc)
    assert BinanceAnnouncementProvider(None, live_enabled=True).fetch_events(start, end) == []


def test_event_discovery_bybit_live_provider_parses_documented_response_offline():
    import json
    from datetime import datetime, timezone
    from crypto_rsi_scanner.event_providers.bybit_announcements import BybitAnnouncementProvider

    class FakeResponse:
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
        return FakeResponse({
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "total": 2,
                "list": [
                    {
                        "title": "New Listing: Test Live (TLIVE) — Deposit and Trade TLIVE",
                        "description": "Bybit is excited to announce the listing of TLIVE on Spot.",
                        "type": {"title": "New Listings", "key": "new_crypto"},
                        "tags": ["Spot", "Spot Listings"],
                        "url": "https://announcements.bybit.com/en-US/article/test-live/",
                        "dateTimestamp": 1781514000000,
                        "startDateTimestamp": 1781524800000,
                    },
                    {
                        "title": "Bybit savings campaign for TLIVE holders",
                        "description": "Earn rewards for completing tasks.",
                        "type": {"title": "Latest Activities", "key": "latest_activities"},
                        "dateTimestamp": 1781517600000,
                    },
                ],
            },
        })

    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 16, tzinfo=timezone.utc)
    provider = BybitAnnouncementProvider(
        None,
        live_enabled=True,
        base_url="https://api.bybit.test",
        locale="en-US",
        announcement_type="new_crypto",
        limit=2,
        timeout=3.5,
        opener=fake_opener,
    )
    events = provider.fetch_events(start, end)
    assert len(events) == 1
    assert seen["url"] == "https://api.bybit.test/v5/announcements/index?locale=en-US&page=1&limit=2&type=new_crypto"
    assert seen["timeout"] == 3.5
    event = events[0]
    assert event.provider == "bybit_announcements"
    assert event.source_url == "https://announcements.bybit.com/en-US/article/test-live/"
    assert event.published_at.isoformat() == "2026-06-15T09:00:00+00:00"
    assert event.raw_json["event"]["event_type"] == "exchange_listing"
    assert event.raw_json["event"]["event_time"] == "2026-06-15T12:00:00+00:00"
    assert event.raw_json["event"]["event_time_confidence"] == 1.0

    def failing_opener(request, timeout):
        raise TimeoutError("offline timeout")

    assert BybitAnnouncementProvider(
        None,
        live_enabled=True,
        opener=failing_opener,
    ).fetch_events(start, end) == []


def test_event_discovery_structured_calendar_providers_parse_fixtures():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.coinmarketcal import CoinMarketCalProvider
    from crypto_rsi_scanner.event_providers.tokenomist import TokenomistProvider

    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    calendar_events = CoinMarketCalProvider(coinmarketcal_path, required=True).fetch_events(start, end)
    unlock_events = TokenomistProvider(tokenomist_path, required=True).fetch_events(start, end)
    assert len(calendar_events) == 1
    assert len(unlock_events) == 1
    assert calendar_events[0].provider == "coinmarketcal"
    assert calendar_events[0].raw_json["event"]["event_type"] == "mainnet_launch"
    assert calendar_events[0].raw_json["event"]["event_time_source"] == "structured_calendar"
    assert calendar_events[0].raw_json["event"]["source_class"] == "structured_calendar"
    assert calendar_events[0].raw_json["calendar"]["symbol"] == "TESTCAL"
    assert calendar_events[0].raw_json["calendar"]["event_category"] == "mainnet"
    assert "TESTCAL" in (calendar_events[0].body or "")
    assert unlock_events[0].provider == "tokenomist"
    assert unlock_events[0].raw_json["event"]["event_type"] == "token_unlock"
    assert unlock_events[0].raw_json["event"]["event_time_source"] == "structured_unlock"
    assert unlock_events[0].raw_json["event"]["source_class"] == "structured_unlock"
    assert unlock_events[0].raw_json["supply"]["unlock_pct_circulating"] == 0.12
    assert unlock_events[0].raw_json["supply"]["unlock_type"] == "cliff"
    assert unlock_events[0].raw_json["supply"]["unlock_materiality"] == "large"

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_calendar.json"
        bad_path.write_text(json.dumps({"events": ["not an object"]}), encoding="utf-8")
        assert CoinMarketCalProvider(bad_path).fetch_events(start, end) == []
        try:
            CoinMarketCalProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed calendar fixture should fail")


def test_event_discovery_normalizes_and_dedupes_events():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider

    events_path, _ = _event_discovery_fixture_paths()
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    normalized = [event_discovery.normalize_raw_event(event) for event in raw]
    assert len(normalized) == 6
    deduped = event_discovery.dedupe_events(normalized)
    assert len(deduped) == 5
    spacex = [event for event in deduped if event.event_name == "SpaceX IPO trading start"][0]
    assert spacex.event_type == "ipo_proxy"
    assert spacex.external_asset == "SpaceX"
    assert len(spacex.raw_ids) == 2
    assert spacex.confidence == 1.0


def test_event_discovery_canonical_dedupe_merges_variant_headlines_and_payloads():
    import copy
    from dataclasses import replace
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider, content_hash
    from crypto_rsi_scanner.event_alpha.radar.resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    base = raw[0]

    def variant(raw_id, title, body, *, keep_sections):
        payload = copy.deepcopy(base.raw_json)
        payload["raw_id"] = raw_id
        payload["title"] = title
        payload["body"] = body
        payload["event"]["event_id"] = raw_id
        payload["event"]["event_name"] = title
        payload["event"]["description"] = body
        for section in ("market", "derivatives", "supply", "rsi", "technical"):
            if section not in keep_sections:
                payload.pop(section, None)
        return replace(
            base,
            raw_id=raw_id,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json=payload,
            content_hash=content_hash(payload),
        )

    first = variant(
        "spacex-ipo-rich-market",
        "TESTVELVET lets traders access SpaceX pre-IPO market before debut",
        "TESTVELVET offers synthetic exposure to SpaceX before IPO trading starts.",
        keep_sections={"market", "derivatives", "supply", "rsi"},
    )
    second = variant(
        "spacex-nasdaq-rich-technical",
        "SpaceX opens Nasdaq trading on June 15 as TESTVELVET proxy token demand peaks",
        "TESTVELVET proxy token failed reclaim after the SpaceX pre-IPO proxy event.",
        keep_sections={"technical"},
    )
    result = event_discovery.run_discovery(
        [first, second],
        load_asset_aliases(aliases_path),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )

    assert len(result.normalized_events) == 1
    event = result.normalized_events[0]
    assert set(event.raw_ids) == {"spacex-ipo-rich-market", "spacex-nasdaq-rich-technical"}
    assert set(event.source_urls) == {
        "https://example.test/spacex-ipo-rich-market",
        "https://example.test/spacex-nasdaq-rich-technical",
    }
    candidate = result.candidates[0]
    assert candidate.data_quality["source_count"] == 2
    assert candidate.fade_candidate.market.price == 7.2
    assert candidate.fade_candidate.technical.failed_reclaim_event_vwap is True
    assert candidate.fade_candidate.technical.entry_reference_price == 7.2
    assert candidate.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED


def test_event_discovery_resolves_real_assets_from_clean_universe_fixture():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider

    events_path, _aliases_path = _event_discovery_fixture_paths()
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    assets = event_discovery.load_discovery_assets(
        None,
        universe_path=_coingecko_universe_fixture_path(),
    )
    assert {asset.coin_id for asset in assets} == {"bitcoin", "ethereum", "solana"}

    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    by_coin = {candidate.asset.coin_id: candidate for candidate in result.candidates}
    assert set(by_coin) == {"bitcoin"}
    btc = by_coin["bitcoin"]
    assert btc.asset.symbol == "BTC"
    assert btc.asset.price == 68000.0
    assert btc.classification.is_direct_beneficiary is True
    assert btc.fade_signal.signal_type == FadeSignalType.NO_TRADE


def test_event_discovery_exchange_announcements_are_direct_no_trade():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_alpha.radar.resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    binance_path, bybit_path = _exchange_announcement_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = event_discovery.load_discovery_events(
        None,
        start,
        end,
        binance_announcements_path=binance_path,
        bybit_announcements_path=bybit_path,
    )
    assets = load_asset_aliases(aliases_path)
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}
    assert len(raw) == 2
    assert set(by_symbol) == {"TESTLIST", "TESTPERP"}

    listing = by_symbol["TESTLIST"]
    assert listing.event.event_type == "exchange_listing"
    assert listing.classification.relationship_type == "direct_listing"
    assert listing.classification.is_direct_beneficiary is True
    assert listing.fade_signal.signal_type == FadeSignalType.NO_TRADE

    perp = by_symbol["TESTPERP"]
    assert perp.event.event_type == "perp_listing"
    assert perp.classification.relationship_type == "direct_listing"
    assert perp.classification.is_direct_beneficiary is True
    assert perp.fade_signal.signal_type == FadeSignalType.NO_TRADE
