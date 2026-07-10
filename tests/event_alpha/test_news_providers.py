"""Focused Event Alpha news-provider and event-time safety tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_discovery_news_providers_parse_fixtures():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.cryptopanic import CryptoPanicProvider
    from crypto_rsi_scanner.event_providers.gdelt import GdeltProvider
    from crypto_rsi_scanner.event_providers.project_blog_rss import ProjectBlogRssProvider

    cryptopanic_path, gdelt_path, blog_path = _news_fixture_paths()
    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    cryptopanic = CryptoPanicProvider(cryptopanic_path, required=True).fetch_events(start, end)
    gdelt = GdeltProvider(gdelt_path, required=True).fetch_events(start, end)
    blog = ProjectBlogRssProvider(blog_path, required=True).fetch_events(start, end)
    assert len(cryptopanic) == 2
    assert len(gdelt) == 1
    assert len(blog) == 2
    assert cryptopanic[0].provider == "cryptopanic"
    assert cryptopanic[0].raw_json["event"]["event_type"] == "ipo_proxy"
    assert gdelt[0].provider == "gdelt"
    assert gdelt[0].raw_json["event"]["event_type"] == "sports_event"
    assert blog[0].provider == "project_blog_rss"
    assert blog[0].raw_json["event"]["event_id"] == "testlate-anthropic-demo"

    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad_news.json"
        bad_path.write_text(json.dumps({"results": ["not an object"]}), encoding="utf-8")
        assert CryptoPanicProvider(bad_path).fetch_events(start, end) == []
        try:
            CryptoPanicProvider(bad_path, required=True).fetch_events(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError("required malformed news fixture should fail")


def test_event_discovery_cryptopanic_live_provider_parses_posts_offline():
    import json
    from datetime import datetime, timezone
    from tempfile import TemporaryDirectory
    from urllib.parse import parse_qs, urlparse
    from pathlib import Path
    from crypto_rsi_scanner.event_providers.cryptopanic import CryptoPanicProvider, cryptopanic_usage_summary

    class FakeResponse:
        status = 200

        def __init__(self, payload):
            self.payload = payload
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.closed = True
            return False

        def read(self):
            assert self.closed is False, "CryptoPanic response body must be read inside context manager"
            return json.dumps(self.payload).encode("utf-8")

    seen = {}

    def fake_opener(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["accept"] = request.headers.get("Accept")
        return FakeResponse({
            "results": [
                {
                    "id": 42,
                    "slug": "testai-openai-preipo",
                    "title": "TESTAI offers synthetic exposure to OpenAI pre IPO event",
                    "description": "TESTAI users can trade tokenized OpenAI pre-IPO exposure.",
                    "published_at": "2026-06-15T10:15:00Z",
                    "created_at": "2026-06-15T10:14:00Z",
                    "original_url": "https://example.test/news/testai-openai",
                    "url": "https://cryptopanic.test/news/testai-openai",
                    "kind": "news",
                    "source": {"title": "Example Crypto", "domain": "example.test", "type": "news"},
                    "instruments": [{"code": "TESTAI", "title": "Test AI", "slug": "test-ai"}],
                    "votes": {"important": 2, "positive": 1},
                    "panic_score": 77,
                    "content": {"clean": "TESTAI expands OpenAI exposure.", "original": "<p>ignored</p>"},
                },
            ],
        })

    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 16, tzinfo=timezone.utc)
    fetched_at = datetime(2026, 6, 15, 10, 20, tzinfo=timezone.utc)
    with TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "cryptopanic_request_ledger.jsonl"
        provider = CryptoPanicProvider(
            None,
            live_enabled=True,
            api_token="token123",
            base_url="https://cryptopanic.test/api/growth_weekly/v2",
            public=True,
            filter_name="hot",
            currencies="BTC,ETH",
            regions="en",
            kind="news",
            search="pre-ipo",
            timeout=2.5,
            opener=fake_opener,
            fetched_at=fetched_at,
            request_ledger_path=ledger,
            profile="fixture",
            artifact_namespace="cryptopanic_growth_fixture",
            min_seconds_between_requests=0,
        )
        events = provider.fetch_events(start, end)
        ledger_rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        assert len(ledger_rows) == 1
        assert ledger_rows[0]["request_url_redacted"].endswith("auth_token=%3Credacted%3E&public=true&currencies=BTC%2CETH&regions=en&kind=news&filter=hot&page=1")
        assert ledger_rows[0]["profile"] == "fixture"
        assert ledger_rows[0]["artifact_namespace"] == "cryptopanic_growth_fixture"
        assert ledger_rows[0]["status_code"] == 200
        assert ledger_rows[0]["result_count"] == 1
        usage = cryptopanic_usage_summary(ledger, now=fetched_at, weekly_limit=600, daily_soft_limit=80)
        assert usage.rolling_7d_requests == 1
        assert usage.remaining_weekly == 599
    assert len(events) == 1
    parsed = urlparse(seen["url"])
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "cryptopanic.test"
    assert parsed.path == "/api/growth_weekly/v2/posts/"
    assert params["auth_token"] == ["token123"]
    assert params["public"] == ["true"]
    assert params["filter"] == ["hot"]
    assert params["currencies"] == ["BTC,ETH"]
    assert params["regions"] == ["en"]
    assert params["kind"] == ["news"]
    assert params["page"] == ["1"]
    for unsupported in ("search", "size", "last_pull", "with_content", "panic_period", "panic_sort"):
        assert unsupported not in params
    assert seen["timeout"] == 2.5
    assert seen["accept"] == "application/json"
    event = events[0]
    assert event.provider == "cryptopanic"
    assert event.source_url == "https://example.test/news/testai-openai"
    assert event.published_at.isoformat() == "2026-06-15T10:15:00+00:00"
    assert event.fetched_at == fetched_at
    assert event.raw_json["event"]["event_type"] == "ipo_proxy"
    assert event.raw_json["instrument_codes"] == ("TESTAI",)
    assert event.raw_json["source_domain"] == "example.test"
    assert event.raw_json["source_class"] == "cryptopanic_tagged"
    assert event.raw_json["content_original_present"] is True

    assert CryptoPanicProvider(None, live_enabled=True, api_token="").fetch_events(start, end) == []
    try:
        CryptoPanicProvider(None, live_enabled=True, api_token="", required=True).fetch_events(start, end)
    except ValueError:
        pass
    else:
        raise AssertionError("required missing CryptoPanic token should fail")

    def failing_opener(request, timeout):
        raise TimeoutError(f"offline timeout url={request.full_url}")

    failed_provider = CryptoPanicProvider(
        None,
        live_enabled=True,
        api_token="token123",
        opener=failing_opener,
    )
    assert failed_provider.fetch_events(start, end) == []
    assert failed_provider.last_warnings
    assert "token123" not in failed_provider.last_warnings[0]
    assert "auth_token" not in failed_provider.last_warnings[0]

    with TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "cryptopanic_request_ledger.jsonl"
        ledger.write_text(json.dumps({
            "timestamp": fetched_at.isoformat(),
            "request_url_redacted": "https://cryptopanic.test/api/growth_weekly/v2/posts/?auth_token=%3Credacted%3E",
            "status_code": 200,
        }) + "\n", encoding="utf-8")
        quota_provider = CryptoPanicProvider(
            None,
            live_enabled=True,
            api_token="token123",
            currencies="BTC",
            opener=fake_opener,
            fetched_at=fetched_at,
            request_ledger_path=ledger,
            weekly_request_limit=1,
            min_seconds_between_requests=0,
        )
        assert quota_provider.fetch_events(start, end) == []
        assert quota_provider.last_skip_reason == "quota_exhausted"
        assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1

    with TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "cryptopanic_request_ledger.jsonl"
        run_cap_provider = CryptoPanicProvider(
            None,
            live_enabled=True,
            api_token="token123",
            currencies="BTC,ETH",
            opener=fake_opener,
            fetched_at=fetched_at,
            request_ledger_path=ledger,
            requests_per_run_limit=1,
            max_currencies_per_request=1,
            min_seconds_between_requests=0,
        )
        assert len(run_cap_provider.fetch_events(start, end)) == 1
        assert run_cap_provider.last_skip_reason == "run_budget_exhausted"
        assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1

    def should_not_call_opener(request, timeout):
        raise AssertionError(f"unexpected CryptoPanic call: {request.full_url}")

    with TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "cryptopanic_request_ledger.jsonl"
        ledger.write_text(json.dumps({
            "timestamp": fetched_at.isoformat(),
            "request_url_redacted": "https://cryptopanic.test/api/growth_weekly/v2/posts/?auth_token=%3Credacted%3E",
            "status_code": 200,
        }) + "\n", encoding="utf-8")
        daily_cap_provider = CryptoPanicProvider(
            None,
            live_enabled=True,
            api_token="token123",
            currencies="BTC",
            opener=should_not_call_opener,
            fetched_at=fetched_at,
            request_ledger_path=ledger,
            requests_per_day_soft_limit=1,
            min_seconds_between_requests=0,
        )
        assert daily_cap_provider.fetch_events(start, end) == []
        assert daily_cap_provider.last_skip_reason == "daily_soft_limit_exceeded"
        assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1


def test_cryptopanic_live_provider_sanitizes_and_dedupes_currency_requests():
    import json
    from datetime import datetime, timezone
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from urllib.parse import parse_qs, urlparse
    from crypto_rsi_scanner.event_providers.cryptopanic import CryptoPanicProvider

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"results": []}).encode("utf-8")

    seen_urls = []

    def fake_opener(request, timeout):
        seen_urls.append(request.full_url)
        return FakeResponse()

    with TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "cryptopanic_request_ledger.jsonl"
        provider = CryptoPanicProvider(
            None,
            live_enabled=True,
            api_token="token123",
            base_url="https://cryptopanic.test/api/growth_weekly/v2",
            currencies="FET,fetch-ai,VELVET,VELVET,SECTOR,H,humanity,,SYN,synapse-2,CHZ,chiliz",
            opener=fake_opener,
            fetched_at=datetime(2026, 6, 15, 12, tzinfo=timezone.utc),
            request_ledger_path=ledger,
            min_seconds_between_requests=0,
        )
        provider.fetch_events(
            datetime(2026, 6, 15, tzinfo=timezone.utc),
            datetime(2026, 6, 16, tzinfo=timezone.utc),
        )
        ledger_rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

    assert len(seen_urls) == 1
    params = parse_qs(urlparse(seen_urls[0]).query)
    assert params["currencies"] == ["FET,VELVET,SYN,CHZ"]
    assert provider.requests_deduped == 1
    assert provider.invalid_currency_requests_skipped >= 5
    assert {item["reason"] for item in provider.rejected_currency_candidates} >= {
        "coin_id_not_currency",
        "sector_not_currency",
        "ticker_collision",
        "empty_currency",
        "duplicate_request",
    }
    assert len(ledger_rows) == 1
    assert ledger_rows[0]["currencies"] == "FET,VELVET,SYN,CHZ"
    assert "fetch-ai" not in ledger_rows[0]["request_url_redacted"]
    assert ledger_rows[0]["normalized_request_key"]


def test_cryptopanic_live_provider_dedupes_same_run_across_instances():
    import json
    from datetime import datetime, timezone
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from crypto_rsi_scanner.event_providers.cryptopanic import CryptoPanicProvider

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"results": [{"id": "cp-chz-1", "title": "CHZ World Cup fan token"}]}).encode("utf-8")

    calls = 0

    def fake_opener(request, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse()

    observed = datetime(2026, 6, 15, 12, tzinfo=timezone.utc)
    with TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "cryptopanic_request_ledger.jsonl"
        providers = [
            CryptoPanicProvider(
                None,
                live_enabled=True,
                api_token="token123",
                base_url="https://cryptopanic.test/api/growth_weekly/v2",
                currencies="CHZ",
                opener=fake_opener,
                fetched_at=observed,
                request_ledger_path=ledger,
                min_seconds_between_requests=0,
            )
            for _ in range(2)
        ]
        for provider in providers:
            events = provider.fetch_events(observed, observed)
            assert len(events) == 1
        ledger_rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

    assert calls == 1
    assert len(ledger_rows) == 1
    assert providers[1].request_cache_hits == 1
    assert providers[1].requests_deduped == 1


def test_cryptopanic_live_provider_dedupes_failed_same_run_requests():
    import json
    from datetime import datetime, timezone
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from crypto_rsi_scanner.event_providers.cryptopanic import CryptoPanicProvider

    class BadResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"not json"

    calls = 0

    def bad_opener(request, timeout):
        nonlocal calls
        calls += 1
        return BadResponse()

    observed = datetime(2026, 6, 15, 12, tzinfo=timezone.utc)
    with TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "cryptopanic_request_ledger.jsonl"
        providers = [
            CryptoPanicProvider(
                None,
                live_enabled=True,
                api_token="token123",
                base_url="https://cryptopanic.test/api/growth_weekly/v2",
                currencies="CHZ",
                opener=bad_opener,
                fetched_at=observed,
                request_ledger_path=ledger,
                min_seconds_between_requests=0,
            )
            for _ in range(2)
        ]
        for provider in providers:
            assert provider.fetch_events(observed, observed) == []
        ledger_rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

    assert calls == 1
    assert len(ledger_rows) == 1
    assert ledger_rows[0]["error_class"] == "json_parse_error"
    assert ledger_rows[0]["content_type"] is None
    assert ledger_rows[0]["body_excerpt_redacted"] == "not json"
    assert ledger_rows[0]["parse_error_message"]
    assert ledger_rows[0]["response_bytes"] == 8
    assert ledger_rows[0]["quota_counted"] is True
    assert providers[1].request_cache_hits == 1


def test_cryptopanic_live_provider_records_safe_parse_and_http_diagnostics():
    import io
    import json
    from datetime import datetime, timezone
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from urllib.error import HTTPError

    from crypto_rsi_scanner.event_providers.cryptopanic import CryptoPanicProvider

    class FakeHeaders(dict):
        def get(self, key, default=None):
            return super().get(key, default) or super().get(key.lower(), default)

    class TextResponse:
        status = 200

        def __init__(self, body: bytes, content_type: str):
            self._body = body
            self.headers = FakeHeaders({"Content-Type": content_type})
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.closed = True
            return False

        def read(self):
            assert self.closed is False
            return self._body

    observed = datetime(2026, 6, 15, 12, tzinfo=timezone.utc)
    fake_token = "0123456789abcdef0123456789abcdef01234567"

    def run_once(opener):
        with TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "cryptopanic_request_ledger.jsonl"
            provider = CryptoPanicProvider(
                None,
                live_enabled=True,
                api_token=fake_token,
                base_url="https://cryptopanic.test/api/growth_weekly/v2",
                currencies="CHZ",
                opener=opener,
                fetched_at=observed,
                request_ledger_path=ledger,
                min_seconds_between_requests=0,
            )
            assert provider.fetch_events(observed, observed) == []
            return provider, [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

    empty_provider, empty_rows = run_once(lambda request, timeout: TextResponse(b"", "application/json"))
    assert empty_provider.last_error_class == "empty_response"
    assert empty_rows[0]["error_class"] == "empty_response"
    assert empty_rows[0]["parse_error_message"] == "empty response body"
    assert empty_rows[0]["response_bytes"] == 0

    html_provider, html_rows = run_once(lambda request, timeout: TextResponse(f"<html>bad token {fake_token}</html>".encode(), "text/html"))
    assert html_provider.last_error_class == "json_parse_error"
    assert html_rows[0]["content_type"] == "text/html"
    assert html_rows[0]["error_class"] == "json_parse_error"
    assert fake_token not in html_rows[0]["body_excerpt_redacted"]
    assert "<redacted>" in html_rows[0]["body_excerpt_redacted"]

    def http_error(request, timeout):
        raise HTTPError(
            request.full_url,
            403,
            "Forbidden",
            FakeHeaders({"Content-Type": "text/html"}),
            io.BytesIO(f"<html>forbidden auth_token={fake_token}</html>".encode()),
        )

    http_provider, http_rows = run_once(http_error)
    assert http_provider.last_error_class == "rate_limited_or_forbidden"
    assert http_rows[0]["status_code"] == 403
    assert http_rows[0]["error_class"] == "rate_limited_or_forbidden"
    assert http_rows[0]["content_type"] == "text/html"
    assert http_rows[0]["provider_health_effect"] == "degraded_backoff"
    assert http_rows[0]["quota_counted"] is True
    assert fake_token not in http_rows[0]["body_excerpt_redacted"]


def test_cryptopanic_catalyst_search_currency_filter_uses_validated_identity_or_empty():
    import crypto_rsi_scanner.event_alpha.radar.catalyst_search as event_catalyst_search
    from crypto_rsi_scanner.event_providers.cryptopanic import (
        normalize_cryptopanic_currency_code,
        plan_cryptopanic_currency_codes,
    )

    assert normalize_cryptopanic_currency_code("FET", "fetch-ai") == "FET"
    assert normalize_cryptopanic_currency_code("SYN", "synapse-2") == "SYN"
    assert normalize_cryptopanic_currency_code("CHZ", "chiliz") == "CHZ"
    assert normalize_cryptopanic_currency_code("SECTOR") is None
    assert normalize_cryptopanic_currency_code("") is None
    assert normalize_cryptopanic_currency_code("H", "humanity", identity_validated=False) is None
    assert normalize_cryptopanic_currency_code("H", "humanity", identity_validated=True) == "H"

    plan = plan_cryptopanic_currency_codes(
        (
            {"symbol": "VELVET", "identity_validated": True},
            {"symbol": "VELVET", "identity_validated": True},
            {"symbol": "fetch-ai", "identity_validated": False},
            {"symbol": "SECTOR", "identity_validated": False},
            {"symbol": "", "identity_validated": False},
            {"symbol": "H", "coin_id": "humanity", "identity_validated": False},
        ),
        identity_validated=False,
    )
    assert plan.accepted == ("VELVET",)
    reasons = {item["reason"] for item in plan.rejected}
    assert {"duplicate_request", "coin_id_not_currency", "sector_not_currency", "empty_currency", "ticker_collision"} <= reasons
    assert plan.duplicate_count == 1

    with_identity = event_catalyst_search.SearchQuery(
        anomaly_raw_id="raw:test",
        query="RUNE exploit update",
        symbol="RUNE",
        rank=1,
        coin_id="thorchain",
        aliases=("RUNE", "THORChain"),
    )
    missing_identity = event_catalyst_search.SearchQuery(
        anomaly_raw_id="raw:sector",
        query="SpaceX crypto exposure",
        symbol="",
        rank=1,
    )
    assert event_catalyst_search._cryptopanic_currencies_for_query(with_identity) == "RUNE"
    assert event_catalyst_search._cryptopanic_currencies_for_query(missing_identity) == ""


def test_event_discovery_gdelt_live_provider_parses_article_list_offline():
    import json
    from datetime import datetime, timezone
    from urllib.parse import parse_qs, urlparse
    from crypto_rsi_scanner.event_providers.gdelt import GdeltProvider

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
        return FakeResponse({
            "articles": [
                {
                    "url": "https://example.test/news/testai-openai-preipo",
                    "title": "TESTAI offers synthetic exposure to OpenAI pre IPO event",
                    "seendate": "20260615143000",
                    "domain": "example.test",
                    "language": "English",
                    "sourceCountry": "US",
                },
            ],
        })

    start = datetime(2026, 6, 15, tzinfo=timezone.utc)
    end = datetime(2026, 6, 16, tzinfo=timezone.utc)
    fetched_at = datetime(2026, 6, 15, 14, 45, tzinfo=timezone.utc)
    provider = GdeltProvider(
        None,
        live_enabled=True,
        base_url="https://api.gdelt.test/api/v2/doc/doc",
        query='("pre-ipo" OR "synthetic exposure")',
        max_records=7,
        timeout=3.5,
        opener=fake_opener,
        fetched_at=fetched_at,
    )
    events = provider.fetch_events(start, end)
    assert len(events) == 1
    parsed = urlparse(seen["url"])
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "api.gdelt.test"
    assert params["query"] == ['("pre-ipo" OR "synthetic exposure")']
    assert params["mode"] == ["artlist"]
    assert params["format"] == ["json"]
    assert params["maxrecords"] == ["7"]
    assert params["sort"] == ["datedesc"]
    assert params["startdatetime"] == ["20260615000000"]
    assert params["enddatetime"] == ["20260616000000"]
    assert seen["timeout"] == 3.5
    event = events[0]
    assert event.provider == "gdelt"
    assert event.source_url == "https://example.test/news/testai-openai-preipo"
    assert event.published_at.isoformat() == "2026-06-15T14:30:00+00:00"
    assert event.fetched_at == fetched_at
    assert event.raw_json["event"]["event_type"] == "ipo_proxy"

    def empty_opener(request, timeout):
        return FakeResponse({"articles": []})

    assert GdeltProvider(None, live_enabled=True, opener=empty_opener).fetch_events(start, end) == []

    def failing_opener(request, timeout):
        raise TimeoutError("offline timeout")

    assert GdeltProvider(None, live_enabled=True, opener=failing_opener).fetch_events(start, end) == []


def test_event_discovery_project_blog_live_rss_provider_parses_feeds_offline():
    from datetime import datetime, timezone
    from crypto_rsi_scanner.event_providers.project_blog_rss import ProjectBlogRssProvider

    class FakeResponse:
        status = 200

        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self.body.encode("utf-8")

    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>TESTRSS Blog</title>
    <item>
      <guid>testrss-openai-preipo</guid>
      <title>TESTRSS offers synthetic exposure to OpenAI pre IPO event by June 20, 2026</title>
      <description>The project blog describes synthetic exposure to OpenAI.</description>
      <link>https://example.test/blog/testrss-openai</link>
      <pubDate>Tue, 16 Jun 2026 12:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""
    atom = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>TESTATOM Updates</title>
  <entry>
    <id>tag:example.test,2026:testatom</id>
    <title>TESTATOM fan token rallies before Test FC World Cup match kickoff</title>
    <summary>The fan token is a proxy attention trade for the dated match fixture.</summary>
    <link rel="alternate" href="https://example.test/blog/testatom-world-cup" />
    <published>2026-06-16T13:30:00Z</published>
  </entry>
</feed>
"""
    seen = []

    def fake_opener(request, timeout):
        seen.append((request.full_url, timeout, request.headers.get("Accept")))
        if request.full_url.endswith("/rss"):
            return FakeResponse(rss)
        if request.full_url.endswith("/atom"):
            return FakeResponse(atom)
        return FakeResponse("<rss><channel /></rss>")

    start = datetime(2026, 6, 16, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    fetched_at = datetime(2026, 6, 16, 14, 0, tzinfo=timezone.utc)
    provider = ProjectBlogRssProvider(
        None,
        live_enabled=True,
        feed_urls=("https://example.test/rss", "https://example.test/atom"),
        timeout=4.0,
        opener=fake_opener,
        fetched_at=fetched_at,
    )
    events = provider.fetch_events(start, end)
    assert len(events) == 2
    assert len(provider.last_feed_health) == 2
    assert all(item.rows_fetched == 1 for item in provider.last_feed_health)
    assert all(item.rows_kept == 1 for item in provider.last_feed_health)
    assert all(item.feed_quality_score > 0 for item in provider.last_feed_health)
    assert [url for url, _timeout, _accept in seen] == ["https://example.test/rss", "https://example.test/atom"]
    assert all(timeout == 4.0 for _url, timeout, _accept in seen)
    assert all("application/rss+xml" in accept for _url, _timeout, accept in seen)
    by_title = {event.title: event for event in events}
    rss_event = by_title["TESTRSS offers synthetic exposure to OpenAI pre IPO event by June 20, 2026"]
    assert rss_event.provider == "project_blog_rss"
    assert rss_event.source_url == "https://example.test/blog/testrss-openai"
    assert rss_event.published_at.isoformat() == "2026-06-16T12:30:00+00:00"
    assert rss_event.fetched_at == fetched_at
    assert rss_event.raw_json["event"]["event_type"] == "ipo_proxy"
    assert rss_event.raw_json["event"]["event_time"] == "2026-06-20T00:00:00+00:00"
    assert rss_event.raw_json["event"]["event_time_confidence"] == 0.60
    assert rss_event.raw_json["event"]["event_time_source"] == "text_date"
    atom_event = by_title["TESTATOM fan token rallies before Test FC World Cup match kickoff"]
    assert atom_event.source_url == "https://example.test/blog/testatom-world-cup"
    assert atom_event.published_at.isoformat() == "2026-06-16T13:30:00+00:00"
    assert atom_event.raw_json["event"]["event_type"] == "sports_event"

    def failing_opener(request, timeout):
        raise TimeoutError("offline timeout")

    assert ProjectBlogRssProvider(
        None,
        live_enabled=True,
        feed_urls=("https://example.test/rss",),
        opener=failing_opener,
    ).fetch_events(start, end) == []

    class StatusResponse(FakeResponse):
        def __init__(self, body, status):
            super().__init__(body)
            self.status = status

    mixed_seen = []

    def mixed_opener(request, timeout):
        mixed_seen.append(request.full_url)
        if request.full_url.endswith("/missing"):
            return StatusResponse("not found", 403)
        return StatusResponse(rss, 200)

    mixed = ProjectBlogRssProvider(
        None,
        live_enabled=True,
        feed_urls=("https://example.test/missing", "https://example.test/rss"),
        fail_fast_on_error=True,
        opener=mixed_opener,
        fetched_at=fetched_at,
    )
    mixed_events = mixed.fetch_events(start, end)
    assert len(mixed_events) == 1
    assert mixed_seen == ["https://example.test/missing", "https://example.test/rss"]
    assert any("feed_failure" in warning for warning in mixed.last_warnings)
    assert not any("skipped remaining feeds" in warning for warning in mixed.last_warnings)
    assert len(mixed.last_feed_health) == 2
    assert mixed.last_feed_health[0].quarantined is True
    assert mixed.last_feed_health[0].cooldown_reason == "feed_403_quarantined"
    assert mixed.last_feed_health[1].rows_kept == 1

    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health

    health_path = Path(tempfile.mkdtemp()) / "provider_health.json"
    health_cfg = event_provider_health.EventProviderHealthConfig(
        path=health_path,
        max_consecutive_failures=1,
        backoff_minutes=30,
    )
    wrapped_mixed = event_provider_health.HealthCheckedEventProvider(
        ProjectBlogRssProvider(
            None,
            live_enabled=True,
            feed_urls=("https://example.test/missing", "https://example.test/rss"),
            fail_fast_on_error=True,
            opener=mixed_opener,
            fetched_at=fetched_at,
        ),
        cfg=health_cfg,
    )
    assert len(wrapped_mixed.fetch_events(start, end, now=fetched_at)) == 1
    rows = event_provider_health.load_provider_health(health_path)
    assert rows["rss:event_source"]["consecutive_failures"] == 0
    assert rows["rss:event_source"]["disabled_until"] is None

    dns_seen = []

    def dns_opener(request, timeout):
        dns_seen.append(request.full_url)
        raise TimeoutError("dns lookup failed")

    dns_failed = ProjectBlogRssProvider(
        None,
        live_enabled=True,
        feed_urls=("https://example.test/rss", "https://example.test/atom"),
        fail_fast_on_error=True,
        opener=dns_opener,
    )
    assert dns_failed.fetch_events(start, end) == []
    assert dns_seen == ["https://example.test/rss"]
    assert any("provider_failure" in warning for warning in dns_failed.last_warnings)
    assert any("skipped remaining feeds" in warning for warning in dns_failed.last_warnings)
    assert len(dns_failed.last_feed_health) == 1
    assert dns_failed.last_feed_health[0].failure_type == "provider_failure"


def test_event_discovery_news_external_asset_inference_handles_generic_ipo_entities():
    from datetime import datetime, timezone
    from crypto_rsi_scanner.event_providers._news_common import news_events_from_items

    start = datetime(2026, 6, 16, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    rows = [
        {
            "id": "mercury-exposure",
            "title": "TESTMERC offers synthetic exposure to Mercury before IPO on June 20, 2026",
            "description": "The token is being used as a temporary proxy for Mercury pre-IPO demand.",
            "url": "https://example.test/mercury-preipo",
            "published_at": "2026-06-16T12:00:00Z",
        },
        {
            "id": "cerebras-ipo-market",
            "title": "Will Cerebras IPO before July 31?",
            "description": "Prediction markets and crypto traders are watching the Cerebras public debut.",
            "url": "https://example.test/cerebras-ipo",
            "published_at": "2026-06-16T13:00:00Z",
        },
        {
            "id": "team-match",
            "title": "USA vs Paraguay match attracts fan token traders",
            "description": "The match fixture is a dated external sports catalyst.",
            "url": "https://example.test/usa-paraguay",
            "published_at": "2026-06-16T14:00:00Z",
        },
        {
            "id": "preipo-market-shutdown",
            "title": "Hyperliquid-Based Ventuals Winds Down On-Chain Pre-IPO Markets",
            "description": "The article is about a venue shutting down generic pre-IPO markets, not a named external IPO catalyst.",
            "url": "https://example.test/ventuals-shutdown",
            "published_at": "2026-06-16T15:00:00Z",
        },
    ]

    events = news_events_from_items(rows, provider="project_blog_rss", start=start, end=end)
    by_id = {event.raw_id: event for event in events}
    assert by_id["project_blog_rss:mercury-exposure"].raw_json["event"]["external_asset"] == "Mercury"
    assert by_id["project_blog_rss:mercury-exposure"].raw_json["event"]["event_type"] == "ipo_proxy"
    assert by_id["project_blog_rss:mercury-exposure"].raw_json["event"]["event_time"] == "2026-06-20T00:00:00+00:00"
    assert by_id["project_blog_rss:cerebras-ipo-market"].raw_json["event"]["external_asset"] == "Cerebras"
    assert by_id["project_blog_rss:cerebras-ipo-market"].raw_json["event"]["event_type"] == "ipo_proxy"
    assert by_id["project_blog_rss:team-match"].raw_json["event"]["external_asset"] == "USA vs Paraguay"
    assert by_id["project_blog_rss:team-match"].raw_json["event"]["event_type"] == "sports_event"
    assert by_id["project_blog_rss:preipo-market-shutdown"].raw_json["event"]["external_asset"] is None
    assert by_id["project_blog_rss:preipo-market-shutdown"].raw_json["event"]["event_type"] == "ipo_proxy"


def test_event_discovery_proxy_article_with_text_date_becomes_dated_review_candidate():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset
    from crypto_rsi_scanner.event_providers.project_blog_rss import ProjectBlogRssProvider

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <guid>hype-spacex-dated-preipo</guid>
      <title>Hyperliquid's HYPE token rallies as pre-IPO perpetual market for SpaceX launches by June 20, 2026</title>
      <description>Trade.xyz launches synthetic exposure to SpaceX through crypto derivatives.</description>
      <link>https://example.test/hype-spacex-dated-preipo</link>
      <pubDate>Tue, 16 Jun 2026 12:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
""".encode("utf-8")

    start = datetime(2026, 6, 16, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = ProjectBlogRssProvider(
        None,
        live_enabled=True,
        feed_urls=("https://example.test/rss",),
        opener=lambda _request, _timeout: FakeResponse(),
        fetched_at=datetime(2026, 6, 16, 13, 0, tzinfo=timezone.utc),
    ).fetch_events(start, end)
    assert raw[0].raw_json["event"]["event_time"] == "2026-06-20T00:00:00+00:00"
    assert raw[0].raw_json["event"]["event_time_confidence"] == 0.60
    assert raw[0].raw_json["event"]["event_time_source"] == "text_date"

    result = event_discovery.run_discovery(
        raw,
        [
            DiscoveredAsset(
                coin_id="hyperliquid",
                symbol="HYPE",
                name="Hyperliquid",
                market_cap=1_000_000_000,
                volume_24h=200_000_000,
                price=35.0,
                categories=("perp-dex",),
                contract_addresses={},
                source="test",
                aliases=("hyperliquid", "hype"),
            )
        ],
        now=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc),
    )

    candidate = result.candidates[0]
    assert candidate.event.event_time.isoformat() == "2026-06-20T00:00:00+00:00"
    assert candidate.event.event_time_source == "text_date"
    assert candidate.data_quality["has_event_time"] is True
    assert candidate.classification.is_proxy_narrative is True
    assert candidate.classification.relationship_type == "proxy_exposure"
    assert candidate.classification.asset_role == "proxy_instrument"
    assert candidate.fade_candidate.event.confidence == 0.60
    assert candidate.fade_signal.signal_type == FadeSignalType.NO_TRADE
    assert candidate.data_quality["event_time_confidence_pass"] is False
    assert candidate.data_quality["forced_no_trade_reason"] == "low_event_time_confidence"
    assert "event time confidence below discovery trigger threshold; review-only" in candidate.fade_signal.warnings

    rows = event_discovery.event_fade_validation_sample_rows(result)
    assert rows[0]["event_time_source"] == "text_date"
    assert rows[0]["event_time_confidence"] == 0.60


def test_event_discovery_explicit_event_time_can_trigger_but_text_date_is_review_only():
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
    assets = load_asset_aliases(aliases_path)
    explicit = event_discovery.run_discovery(
        [raw[0]],
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    ).candidates[0]
    assert explicit.event.event_time_source == "explicit"
    assert explicit.fade_signal.signal_type == FadeSignalType.SHORT_TRIGGERED
    assert explicit.data_quality["forced_no_trade_reason"] is None

    payload = copy.deepcopy(raw[0].raw_json)
    payload["event"]["event_time_confidence"] = 0.60
    payload["event"]["event_time_source"] = "text_date"
    text_date_raw = replace(
        raw[0],
        raw_id="velvet-text-date-low-confidence",
        raw_json=payload,
        content_hash=content_hash(payload),
    )
    text_date = event_discovery.run_discovery(
        [text_date_raw],
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    ).candidates[0]
    assert text_date.event.event_time_source == "text_date"
    assert text_date.fade_signal.fade_score >= 80
    assert text_date.fade_signal.signal_type == FadeSignalType.NO_TRADE
    assert text_date.data_quality["forced_no_trade_reason"] == "low_event_time_confidence"


def test_event_discovery_forces_no_trade_on_low_classifier_confidence():
    from dataclasses import replace
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_alpha.radar import discovery as discovery_impl
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_providers.manual_json import ManualJsonEventProvider
    from crypto_rsi_scanner.event_alpha.radar.resolver import load_asset_aliases

    events_path, aliases_path = _event_discovery_fixture_paths()
    raw = ManualJsonEventProvider(events_path, required=True).fetch_events(
        datetime(2026, 6, 12, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
    assets = load_asset_aliases(aliases_path)
    original_classifier = discovery_impl.classify_event_asset

    def low_confidence_classifier(event, asset, link):
        classification = original_classifier(event, asset, link)
        if asset.coin_id == "testvelvet":
            return replace(classification, confidence=0.79)
        return classification

    discovery_impl.classify_event_asset = low_confidence_classifier
    try:
        candidate = event_discovery.run_discovery(
            [raw[0]],
            assets,
            now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
        ).candidates[0]
    finally:
        discovery_impl.classify_event_asset = original_classifier

    assert candidate.fade_signal.fade_score >= 80
    assert candidate.data_quality["has_technical_snapshot"] is True
    assert candidate.data_quality["classifier_pass"] is False
    assert candidate.data_quality["forced_no_trade_reason"] == "low_classifier_confidence"
    assert candidate.fade_signal.signal_type == FadeSignalType.NO_TRADE
    assert "classifier confidence below discovery trigger threshold; review-only" in candidate.fade_signal.warnings


def test_event_discovery_proxy_article_without_event_time_stays_reviewable_no_trade():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset
    from crypto_rsi_scanner.event_providers.project_blog_rss import ProjectBlogRssProvider

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <guid>hype-spacex-preipo</guid>
      <title>Hyperliquid's HYPE token rallies as pre-IPO perpetual market for SpaceX launches</title>
      <description>Trade.xyz launches synthetic exposure to SpaceX through crypto derivatives.</description>
      <link>https://example.test/hype-spacex-preipo</link>
      <pubDate>Tue, 16 Jun 2026 12:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
""".encode("utf-8")

    start = datetime(2026, 6, 16, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = ProjectBlogRssProvider(
        None,
        live_enabled=True,
        feed_urls=("https://example.test/rss",),
        opener=lambda _request, _timeout: FakeResponse(),
        fetched_at=datetime(2026, 6, 16, 13, 0, tzinfo=timezone.utc),
    ).fetch_events(start, end)
    assert raw[0].raw_json["event"]["event_type"] == "ipo_proxy"
    assert raw[0].raw_json["event"]["external_asset"] == "SpaceX"
    assert raw[0].raw_json["event"]["event_time"] is None

    result = event_discovery.run_discovery(
        raw,
        [
            DiscoveredAsset(
                coin_id="hyperliquid",
                symbol="HYPE",
                name="Hyperliquid",
                market_cap=1_000_000_000,
                volume_24h=200_000_000,
                price=35.0,
                categories=("perp-dex",),
                contract_addresses={},
                source="test",
                aliases=("hyperliquid", "hype"),
            )
        ],
        now=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc),
    )

    candidate = result.candidates[0]
    assert candidate.classification.is_proxy_narrative is True
    assert candidate.classification.relationship_type == "proxy_attention"
    assert candidate.classification.asset_role == "proxy_instrument"
    assert candidate.fade_signal.signal_type == FadeSignalType.NO_TRADE
    assert "not an eligible proxy event-fade candidate" in candidate.fade_signal.warnings
